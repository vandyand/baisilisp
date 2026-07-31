(ns acceptance.data-json.workflow
  (:require [clojure.data.json :as json]
            [clojure.string :as str]))

#?(:clj (import [java.io StringReader StringWriter])
   :lpy (import io))

(deftype FixtureJSONValue [value])

(extend-protocol json/JSONWriter
  FixtureJSONValue
  (-write [fixture writer _]
    (.write writer (json/write-str (.-value fixture)))))

(defn public-summary []
  (sort (map name (keys (ns-publics 'clojure.data.json)))))

(defn default-options-summary []
  {:read (sort (map name (keys json/default-read-options)))
   :write (sort (map name (keys json/default-write-options)))})

(defn string-reader [source]
  #?(:clj (StringReader. source)
     :lpy (io/StringIO source)))

(defn string-writer []
  #?(:clj (StringWriter.)
     :lpy (io/StringIO)))

(defn writer-string [writer]
  #?(:clj (str writer)
     :lpy (.getvalue writer)))

(defn writer-output [value & opts]
  (let [writer (string-writer)]
    (apply json/write value writer opts)
    (writer-string writer)))

(defn write-read [value & opts]
  (json/read-str (apply json/write-str value opts)))

(defn error? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn read-summary []
  {:keywords (json/read-str "{\"name\":\"BaisiLisp\",\"items\":[1,true,null]}"
                            :key-fn keyword)
   :stream-read (json/read (string-reader "{\"stream\":1}") :key-fn keyword)
   :read-json (json/read-json "{\"legacy\":1}")
   :bigdec (str (json/read-str "3.14159" :bigdec true))
   :eof (json/read-str "" :eof-error? false :eof-value :eof)
   :extra (json/read-str "[42], trailing"
                         :extra-data-fn (fn [value reader]
                                          [value #?(:clj (slurp reader)
                                                    :lpy (.read reader))]))})

(defn write-summary []
  {:vector (json/write-str [1 true nil "x/y"])
   :json-str (json/json-str [1 2])
   :writer (writer-output {:a 1})
   :write-json (let [writer (string-writer)]
                 (json/write-json {:legacy 1} writer false)
                 (writer-string writer))
   :print-json (with-out-str (json/print-json {:printed 1}))
   :pprint-json-non-empty (not (str/blank?
                                (with-out-str
                                  (json/pprint-json {:pretty [1 2]}))))
   :escaped-unicode (json/write-str {"unicode" "∂"})
   :slash-unescaped (json/write-str ["a/b"] :escape-slash false)
   :pprint-non-empty (not (str/blank?
                           (with-out-str
                             (json/pprint {:a [1 2]}))))})

(defn callback-summary []
  {:value-fn (json/read-str "{\"keep\":1,\"drop\":2}"
                            :key-fn keyword
                            :value-fn (fn omit-drop [key value]
                                        (if (= key :drop) omit-drop value)))
   :write-filter (write-read {:drop nil :keep 1}
                             :value-fn (fn omit-nil [_ value]
                                         (if (nil? value) omit-nil value)))
   :write-key-fn (json/read-str
                  (json/write-str {:alpha-key 1}
                                  :key-fn #(str "k-" (name %))))
   :write-value-fn (json/read-str
                    (json/write-str {:drop nil
                                     :keep 1
                                     :nested {:drop nil :keep 2}}
                                    :value-fn (fn omit-nil [_ value]
                                                (if (nil? value)
                                                  omit-nil
                                                  value))))})

(defn boundary-summary []
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
    {:host-reader-boundaries
     {:reader-pbr? (some? (json/->ReaderPBR (string-reader "[]")))
      :string-pbr? (some? (json/->StringPBR "[1,2]" 0 5))
      :codepoint-decoder? (some? json/codepoint-decoder)}
     :errors {:nil-key (error? #(json/write-str {nil 1}))
              :invalid-array (error? #(throw (json/invalid-array-exception)))
              :extra (error? #(json/read-str "[42], trailing"
                                             :extra-data-fn json/on-extra-throw))
              :extra-remaining (error? #(json/read-str
                                         "[42], trailing"
                                         :extra-data-fn
                                         json/on-extra-throw-remaining))
              :bad-tokens [(error? #(json/read-str "NaN"))
                           (error? #(json/read-str "Infinity"))
                           (error? #(json/read-str "{\"a\":1,}"))
                           (error? #(json/read-str "[1 2]"))]}
     :read-boundaries
     {:single-stream-read (json/read (string-reader "  {\"a\":1}") :key-fn keyword)
      :nested-value-fn (json/read-str
                        "{\"keep\":{\"drop\":1,\"value\":2},\"items\":[{\"drop\":3,\"value\":4}]}"
                        :key-fn keyword
                        :value-fn (fn omit-drop [key value]
                                    (if (= :drop key) omit-drop value)))
      :extra-reader-suffix (json/read-str
                            "{\"a\":1}  \n  tail"
                            :key-fn keyword
                            :extra-data-fn
                            (fn [value reader]
                              [value (str/trim #?(:clj (slurp reader)
                                                  :lpy (.read reader)))]))
      :eof-value (json/read-str "" :eof-error? false :eof-value :done)}
     :write-boundaries
     {:js-default-escaped [(str/includes? encoded-default "\\u2028")
                           (str/includes? encoded-default "\\u2029")]
      :js-raw-roundtrip (= {"line" line-separator
                            "paragraph" paragraph-separator}
                           (json/read-str encoded-js-raw))
      :unicode-raw-roundtrip (= {"unicode" "∂" "slash" "a/b"}
                                (json/read-str encoded-unicode-raw))
      :pretty-roundtrip (= {"a" [1 2] "b" {"c" true}}
                           (json/read-str pretty))
      :pretty-has-newlines (str/includes? pretty "\n")}}))

(defn protocol-summary []
  (let [writer (string-writer)]
    (json/-write (->FixtureJSONValue {:protocol 1})
                 writer
                 json/default-write-options)
    {:protocol-var? (some? json/JSONWriter)
     :direct-write (writer-string writer)
     :default-write-fn (json/write-str (->FixtureJSONValue [1 2]))}))

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(defn seeded-scalar [seed]
  (case (mod seed 8)
    0 (mod seed 100000)
    1 (str "text/" (mod seed 100000) " ∂")
    2 (zero? (mod seed 2))
    3 nil
    4 (str "line" (char 8232) (mod seed 1000))
    5 (str "para" (char 8233) (mod seed 1000))
    6 (str "quote\"" (mod seed 1000))
    7 (str "slash/" (mod seed 1000))))

(defn seeded-value [seed depth]
  (if (zero? depth)
    (seeded-scalar seed)
    (case (mod seed 5)
      0 (seeded-scalar seed)
      1 [(seeded-scalar seed)
         (seeded-value (next-seed seed) (dec depth))]
      2 {"inner" (seeded-value (next-seed seed) (dec depth))}
      3 []
      4 {})))

(defn generated-case [seed]
  (let [s1 (next-seed seed)
        s2 (next-seed s1)
        s3 (next-seed s2)
        s4 (next-seed s3)
        value {"a" (seeded-value s1 2)
               "b" (seeded-value s2 2)
               "c" (seeded-value s3 2)}
        pretty (json/write-str value :indent true)
        raw (json/write-str value :escape-unicode false :escape-slash false)]
    {:seed seed
     :compact-roundtrip (= value (write-read value))
     :pretty-roundtrip (= value (json/read-str pretty))
     :raw-roundtrip (= value (json/read-str raw))
     :compact-size (count (json/write-str value))
     :pretty-has-newlines (or (empty? value) (str/includes? pretty "\n"))
     :next-seed s4}))

(defn generated-summary []
  (loop [remaining 96
         seed 19088743
         result []]
    (if (zero? remaining)
      result
      (let [case (generated-case seed)]
        (recur (dec remaining)
               (:next-seed case)
               (conj result (dissoc case :next-seed)))))))
