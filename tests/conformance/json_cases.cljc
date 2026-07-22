;; Portable clojure.data.json/basilisp.data.json cases. Clojure data.json is
;; loaded through the differential harness' explicit org.clojure/data.json
;; dependency. Compare public surface, option-map shape, read/write semantics,
;; callbacks, extra-data handling, error boundaries, and seeded round trips
;; without comparing host exception classes or Java/Python implementation types.

#?(:clj (require '[clojure.data.json :as json]
                 '[clojure.string :as str])
   :lpy (require '[clojure.data.json :as json]
                 '[basilisp.string :as str]))

#?(:clj (import [java.io StringReader StringWriter])
   :lpy (import io))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn public-json-names []
  (sort (map name (keys (ns-publics #?(:clj 'clojure.data.json
                                        :lpy 'basilisp.data.json))))))

(defn errors? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _ true)))

(defn read-all [s & opts]
  (apply json/read-str s opts))

(defn write-read [value & opts]
  (json/read-str (apply json/write-str value opts)))

(defn writer-output [value & opts]
  (let [writer #?(:clj (StringWriter.)
                  :lpy (io/StringIO))]
    (apply json/write value writer opts)
    #?(:clj (str writer)
       :lpy (.getvalue writer))))

(emit-case :public-surface
           (public-json-names))

(emit-case :default-option-keys
           {:read (sort (map name (keys json/default-read-options)))
            :write (sort (map name (keys json/default-write-options)))})

(emit-case :reading
           {:keywords (json/read-str "{\"name\":\"BaisiLisp\",\"items\":[1,true,null]}"
                                     :key-fn keyword)
            :bigdec (str (json/read-str "3.14159" :bigdec true))
            :eof (json/read-str "" :eof-error? false :eof-value :eof)
            :extra (json/read-str "[42], trailing"
                                  :extra-data-fn (fn [value reader]
                                                   [value #?(:clj (slurp reader)
                                                             :lpy (.read reader))]))})

(emit-case :writing
           {:vector (json/write-str [1 true nil "x/y"])
            :writer (writer-output {:a 1})
            :escaped-unicode (json/write-str {"unicode" "∂"})
            :slash-unescaped (json/write-str ["a/b"] :escape-slash false)
            :pprint-non-empty (not (str/blank? (with-out-str (json/pprint {:a [1 2]}))))})

(emit-case :callbacks-and-errors
           {:value-fn (json/read-str "{\"keep\":1,\"drop\":2}"
                                     :key-fn keyword
                                     :value-fn (fn omit-drop [key value]
                                                 (if (= key :drop) omit-drop value)))
            :write-filter (write-read {:drop nil :keep 1}
                                      :value-fn (fn omit-nil [_ value]
                                                  (if (nil? value) omit-nil value)))
            :nil-key-error (errors? #(json/write-str {nil 1}))
            :invalid-array-error (errors? #(throw (json/invalid-array-exception)))
            :extra-error (errors? #(json/read-str "[42], trailing"
                                                  :extra-data-fn json/on-extra-throw))})

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(defn seeded-value [seed]
  (case (mod seed 6)
    0 (mod seed 100000)
    1 (str "text/" (mod seed 100000) " ∂")
    2 (zero? (mod seed 2))
    3 nil
    4 [(mod seed 100) (str "nested" (mod seed 1000))]
    5 {"inner" (mod seed 10000)}))

(emit-case :seeded-round-trips
           (loop [remaining 48
                  seed 19088743
                  result []]
             (if (zero? remaining)
               result
               (let [s1 (next-seed seed)
                     s2 (next-seed s1)
                     s3 (next-seed s2)
                     value {"a" (seeded-value s1)
                            "b" (seeded-value s2)
                            "c" (seeded-value s3)}]
                 (recur (dec remaining)
                        s3
                        (conj result (= value (write-read value))))))))
