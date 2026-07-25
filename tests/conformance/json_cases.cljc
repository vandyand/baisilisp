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

(deftype FixtureJSONValue [value])

(extend-protocol json/JSONWriter
  FixtureJSONValue
  (-write [fixture writer _]
    (.write writer (json/write-str (.-value fixture)))))

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

(emit-case :host-reader-boundaries
           {:reader-pbr? (some? (json/->ReaderPBR #?(:clj (StringReader. "[]")
                                                     :lpy (io/StringIO "[]"))))
            :string-pbr? (some? (json/->StringPBR "[1,2]" 0 5))
            :codepoint-decoder? (some? json/codepoint-decoder)})

(emit-case :reading
           {:keywords (json/read-str "{\"name\":\"BaisiLisp\",\"items\":[1,true,null]}"
                                     :key-fn keyword)
            :stream-read (json/read #?(:clj (StringReader. "{\"stream\":1}")
                                       :lpy (io/StringIO "{\"stream\":1}"))
                                   :key-fn keyword)
            :read-json (json/read-json "{\"legacy\":1}")
            :bigdec (str (json/read-str "3.14159" :bigdec true))
            :eof (json/read-str "" :eof-error? false :eof-value :eof)
            :extra (json/read-str "[42], trailing"
                                  :extra-data-fn (fn [value reader]
                                                   [value #?(:clj (slurp reader)
                                                             :lpy (.read reader))]))})

(emit-case :writing
           {:vector (json/write-str [1 true nil "x/y"])
            :json-str (json/json-str [1 2])
            :writer (writer-output {:a 1})
            :write-json (let [writer #?(:clj (StringWriter.)
                                        :lpy (io/StringIO))]
                          (json/write-json {:legacy 1} writer false)
                          #?(:clj (str writer)
                             :lpy (.getvalue writer)))
            :print-json (with-out-str (json/print-json {:printed 1}))
            :pprint-json-non-empty (not (str/blank?
                                         (with-out-str
                                           (json/pprint-json {:pretty [1 2]}))))
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
                                                  :extra-data-fn json/on-extra-throw))
            :extra-remaining-error
            (errors? #(json/read-str "[42], trailing"
                                      :extra-data-fn json/on-extra-throw-remaining))})

(emit-case :adversarial-read-boundaries
           {:single-stream-read (json/read #?(:clj (StringReader. "  {\"a\":1}")
                                              :lpy (io/StringIO "  {\"a\":1}"))
                                          :key-fn keyword)
            :nested-value-fn
              (json/read-str "{\"keep\":{\"drop\":1,\"value\":2},\"items\":[{\"drop\":3,\"value\":4}]}"
                             :key-fn keyword
                             :value-fn (fn omit-drop [key value]
                                         (if (= :drop key) omit-drop value)))
            :extra-reader-suffix (json/read-str "{\"a\":1}  \n  tail"
                                                :key-fn keyword
                                                :extra-data-fn
                                                (fn [value reader]
                                                  [value (str/trim #?(:clj (slurp reader)
                                                                      :lpy (.read reader)))]))
            :eof-value (json/read-str "" :eof-error? false :eof-value :done)
            :bad-token-errors [(errors? #(json/read-str "NaN"))
                               (errors? #(json/read-str "Infinity"))
                               (errors? #(json/read-str "{\"a\":1,}"))
                               (errors? #(json/read-str "[1 2]"))]})

(emit-case :adversarial-write-options
           (let [line-separator (str "line" (char 8232) "sep")
                 paragraph-separator (str "para" (char 8233) "sep")
                 encoded-default (json/write-str {"line" line-separator
                                                  "paragraph" paragraph-separator})
                 encoded-js-raw (json/write-str {"line" line-separator
                                                 "paragraph" paragraph-separator}
                                                :escape-js-separators false)
                 encoded-unicode-raw (json/write-str {"unicode" "∂"
                                                       "slash" "a/b"}
                                                      :escape-unicode false
                                                      :escape-slash false)
                 pretty (json/write-str {:a [1 2] :b {:c true}} :indent true)]
             {:js-default-escaped [(str/includes? encoded-default "\\u2028")
                                   (str/includes? encoded-default "\\u2029")]
              :js-raw-roundtrip (= {"line" line-separator
                                    "paragraph" paragraph-separator}
                                   (json/read-str encoded-js-raw))
              :unicode-raw-roundtrip (= {"unicode" "∂" "slash" "a/b"}
                                        (json/read-str encoded-unicode-raw))
              :pretty-roundtrip (= {"a" [1 2] "b" {"c" true}}
                                   (json/read-str pretty))
              :pretty-has-newlines (str/includes? pretty "\n")
              :write-key-fn (json/read-str
                             (json/write-str {:alpha-key 1}
                                             :key-fn #(str "k-" (name %))))
              :write-value-fn (json/read-str
                               (json/write-str {:drop nil :keep 1 :nested {:drop nil :keep 2}}
                                               :value-fn (fn omit-nil [key value]
                                                           (if (nil? value) omit-nil value))))}))

(emit-case :writer-protocol
           (let [writer #?(:clj (StringWriter.)
                           :lpy (io/StringIO))]
             (json/-write (->FixtureJSONValue {:protocol 1})
                          writer
                          json/default-write-options)
             {:protocol-var? (some? json/JSONWriter)
              :direct-write #?(:clj (str writer)
                               :lpy (.getvalue writer))
              :default-write-fn (json/write-str (->FixtureJSONValue [1 2]))}))

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
