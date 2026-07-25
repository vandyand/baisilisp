;; Portable clojure.java.io/basilisp.java.io cases. Each case compares the
;; Clojure-shaped alias contract: public surface, path coercions, URL/resource
;; behavior, file creation, readers/writers, streams, copying, factory vars, and
;; a seeded file round-trip corpus.

#?(:clj (require '[clojure.java.io :as io]
                 '[clojure.string :as str])
   :lpy (require '[clojure.java.io :as io]
                 '[basilisp.string :as str]))

#?(:clj (import [java.net URLClassLoader]
                [java.nio.file Files])
   :lpy (import sys tempfile pathlib))

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

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

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

(defn resource-roundtrip [root name]
  #?(:clj (let [loader (URLClassLoader.
                        (into-array java.net.URL
                                    [(.toURL (.toURI (io/file root)))])
                        nil)
               resource (io/resource name loader)]
           [(some? resource)
            (when resource
              (slurp resource))])
     :lpy (let [original-path (.copy sys/path)]
            (try
              (.insert sys/path 0 (str root))
              (let [resource (io/resource name)]
                [(some? resource)
                 (when resource
                   (slurp resource))])
              (finally
                (.clear sys/path)
                (.extend sys/path original-path))))))

(emit-case :public-surface
           (public-io-names))

(emit-case :factory-surface
           {:default-stream-keys (default-stream-impl-keys)
            :factory-vars (mapv #(contains? (ns-publics #?(:clj 'clojure.java.io
                                                           :lpy 'basilisp.java.io))
                                            (symbol %))
                                ["Coercions" "IOFactory" "make-reader" "make-writer"
                                 "make-input-stream" "make-output-stream"])})

(emit-case :direct-factory-and-delete-vars
           (let [root (temp-root)
                 text-target (temp-file root "direct" "factory.txt")
                 stream-target (temp-file root "direct" "stream.txt")]
             (io/make-parents text-target)
             (with-open [writer (io/make-writer text-target
                                                #?(:clj {}
                                                   :lpy {:mode "w"}))]
               (.write writer "factory-text"))
             (with-open [stream (io/make-output-stream stream-target
                                                       #?(:clj {}
                                                          :lpy {:mode "wb"}))]
               (.write stream (output-bytes "factory-bytes")))
             (let [reader-text (with-open [reader (io/make-reader text-target
                                                                   #?(:clj {}
                                                                      :lpy {:mode "r"}))]
                                 (slurp reader))
                   input-text (with-open [stream (io/make-input-stream stream-target
                                                                       #?(:clj {}
                                                                          :lpy {:mode "rb"}))]
                                #?(:clj (let [buffer (byte-array 128)
                                              n (.read stream buffer)]
                                          (String. buffer 0 n "UTF-8"))
                                   :lpy (.decode (.read stream) "utf-8")))
                   existing (io/delete-file stream-target true)
                   missing (io/delete-file stream-target :silent)]
               {:protocol-vars [(some? io/Coercions)
                                (some? io/IOFactory)]
                :reader reader-text
                :input-stream input-text
                :delete-results {:delete-existing existing
                                 :delete-missing missing}})))

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

(emit-case :adversarial-file-mutation-and-delete
           (let [root (temp-root)
                 nested (temp-file root "deep" "path" "value.txt")
                 overwrite-target (temp-file root "deep" "path" "overwrite.txt")
                 copy-target (temp-file root "copy" "bytes.bin")]
             (let [created-parents? (io/make-parents nested)
                   existing-parents? (io/make-parents nested)]
             (with-open [writer (io/writer nested)]
               (.write writer "first"))
             (with-open [writer (io/writer nested :append true)]
               (.write writer "+second"))
             (with-open [writer (io/writer overwrite-target)]
               (.write writer "old"))
             (with-open [writer (io/writer overwrite-target :append false)]
               (.write writer "new"))
             (io/make-parents copy-target)
             (with-open [out (io/output-stream copy-target)]
               (.write out (output-bytes "bytes-copy")))
             (let [append-text (slurp nested)
                   overwrite-text (slurp overwrite-target)
                   input-text (read-stream-text copy-target)
                   delete-existing (io/delete-file copy-target false)
                   delete-missing-silent (io/delete-file copy-target :silent)
                   delete-missing-rejected? (rejected?
                                             #(io/delete-file copy-target false))]
               {:make-parents-created created-parents?
                :make-parents-existing existing-parents?
                :append append-text
                :overwrite overwrite-text
                :input-stream input-text
                :delete-existing delete-existing
                :delete-missing-silent delete-missing-silent
                :delete-missing-rejected? delete-missing-rejected?}))))

(emit-case :streams
           (let [root (temp-root)
                 target (temp-file root "stream.txt")]
             (write-stream-text target "stream-text")
             (read-stream-text target)))

(emit-case :adversarial-url-resource-and-copy
           (let [root (temp-root)
                 source (temp-file root "source.txt")
                 target (temp-file root "target.txt")
                 resource-file (temp-file root "assets" "resource.txt")]
             (io/make-parents source)
             (spit source "source-text")
             (io/copy source target)
             (io/make-parents resource-file)
             (spit resource-file "resource-text")
             {:relative-url-rejected? (rejected? #(io/as-url "relative/path"))
              :absolute-relative-rejected? (rejected?
                                            #(io/as-relative-path
                                              #?(:clj (.getAbsolutePath
                                                       (java.io.File. "absolute"))
                                                 :lpy (.resolve
                                                       (pathlib/Path "absolute")))))
              :file-url-roundtrip (slurp (io/as-url source))
              :path-copy (slurp target)
              :string-copy (let [copy-target (temp-file root "string-copy.txt")]
                             (io/copy "literal payload" copy-target)
                             (slurp copy-target))
              :resource (resource-roundtrip root "assets/resource.txt")}))

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
