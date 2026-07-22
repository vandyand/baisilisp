;; Portable clojure.java.io/basilisp.java.io cases. Each case compares the
;; Clojure-shaped alias contract: public surface, path coercions, URL/resource
;; behavior, file creation, readers/writers, streams, copying, factory vars, and
;; a seeded file round-trip corpus.

#?(:clj (require '[clojure.java.io :as io]
                 '[clojure.string :as str])
   :lpy (require '[clojure.java.io :as io]
                 '[basilisp.string :as str]))

#?(:clj (import [java.nio.file Files])
   :lpy (import tempfile))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn public-io-names []
  (sort (map name (keys (ns-publics #?(:clj 'clojure.java.io
                                        :lpy 'basilisp.java.io))))))

(defn normalize-path-str [path]
  (str/replace (str path) "\\" "/"))

(defn temp-root []
  #?(:clj (str (Files/createTempDirectory
                "basilisp-java-io-case"
                (make-array java.nio.file.attribute.FileAttribute 0)))
     :lpy (tempfile/mkdtemp ** :prefix "basilisp-java-io-case")))

(defn temp-file [root & parts]
  (apply io/file root parts))

(defn url-summary [url]
  #?(:clj {:protocol (.getProtocol url)
           :string (str url)}
     :lpy {:protocol (.-scheme url)
           :string (str url)}))

(defn url-protocol [url]
  (:protocol (url-summary url)))

(defn output-bytes [text]
  #?(:clj (.getBytes text "UTF-8")
     :lpy (byte-string text "utf-8")))

(defn read-stream-text [path]
  #?(:clj (with-open [stream (io/input-stream path)]
            (let [buffer (byte-array 128)
                  n (.read stream buffer)]
              (String. buffer 0 n "UTF-8")))
     :lpy (with-open [stream (io/input-stream path)]
            (.decode (.read stream) "utf-8"))))

(defn write-stream-text [path text]
  (with-open [stream (io/output-stream path)]
    (.write stream (output-bytes text)))
  path)

(defn default-stream-impl-keys []
  (sort (map name (keys io/default-streams-impl))))

(emit-case :public-surface
           (public-io-names))

(emit-case :factory-surface
           {:default-stream-keys (default-stream-impl-keys)
            :factory-vars (mapv #(contains? (ns-publics #?(:clj 'clojure.java.io
                                                           :lpy 'basilisp.java.io))
                                            (symbol %))
                                ["Coercions" "IOFactory" "make-reader" "make-writer"
                                 "make-input-stream" "make-output-stream"])})

(emit-case :path-coercions
           {:file (normalize-path-str (io/file "parent" "child" "leaf.txt"))
            :as-file (normalize-path-str (io/as-file "parent"))
            :relative (normalize-path-str (io/as-relative-path "parent/child"))
            :file-nil (nil? (io/file nil))
            :as-url-nil (nil? (io/as-url nil))})

(emit-case :url-and-resource
           {:url-protocol (url-protocol (io/as-url "https://example.com/path"))
            :file-protocol (url-protocol (io/as-url (io/file "parent")))
            :missing-resource (nil? (io/resource "definitely-missing-resource"))
            :missing-resource-loader (nil? (io/resource
                                            "definitely-missing-resource"
                                            #?(:clj (ClassLoader/getSystemClassLoader)
                                               :lpy nil)))})

(emit-case :file-reader-writer-copy
           (let [root (temp-root)
                 nested (temp-file root "nested" "child" "value.txt")
                 copy-target (temp-file root "copy" "value-copy.txt")]
             (io/make-parents nested)
             (with-open [writer (io/writer nested)]
               (.write writer "alpha"))
             (with-open [writer (io/writer nested :append true)]
               (.write writer "+beta"))
             (io/make-parents copy-target)
             (io/copy nested copy-target)
             {:read (with-open [reader (io/reader nested)]
                      (slurp reader))
              :copy (slurp copy-target)}))

(emit-case :streams
           (let [root (temp-root)
                 target (temp-file root "stream.txt")]
             (write-stream-text target "stream-text")
             (read-stream-text target)))

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(emit-case :seeded-file-round-trips
           (let [root (temp-root)]
             (loop [remaining 24
                    seed 8675309
                    result []]
               (if (zero? remaining)
                 result
                 (let [next (next-seed seed)
                       name (str "case-" (mod next 1000000) ".txt")
                       target (temp-file root name)
                       text (str "payload-" (mod next 65536))]
                   (with-open [writer (io/writer target)]
                     (.write writer text))
                   (recur (dec remaining)
                          next
                          (conj result (slurp target))))))))
