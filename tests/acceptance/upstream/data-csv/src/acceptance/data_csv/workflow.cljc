(ns acceptance.data-csv.workflow
  (:require [clojure.data.csv :as csv]
            [clojure.string :as str]))

#?(:clj (import [java.io StringReader StringWriter])
   :lpy (import io))

(defn public-surface []
  (sort (map name (keys (ns-publics 'clojure.data.csv)))))

(defn string-reader [s]
  #?(:clj (StringReader. s)
     :lpy (io/StringIO s)))

(defn string-writer []
  #?(:clj (StringWriter.)
     :lpy (io/StringIO)))

(defn writer-string [writer]
  #?(:clj (str writer)
     :lpy (.getvalue writer)))

(defn write-output [rows & opts]
  (let [writer (string-writer)]
    (apply csv/write-csv writer rows opts)
    (writer-string writer)))

(defn read-all [source & opts]
  (vec (apply csv/read-csv source opts)))

(defn read-from [source separator quote]
  (vec (csv/read-csv-from source (int separator) (int quote))))

(defn error? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn basic-summary []
  [[:publics (public-surface)]
   [:protocol? (some? csv/Read-CSV-From)]
   [:string (read-all "id,name\n1,Ada\n2,Rich")]
   [:reader (read-all (string-reader "a,b\nc,d"))]
   [:empty [(read-all "") (read-all (string-reader ""))]]])

(defn option-summary []
  (let [default-output (write-output [["a" "b"]
                                      ["has,comma" "has\"quote"]
                                      ["line\nbreak" "last"]])
        custom-output  (write-output [["a" "b"] ["c;d" "e"]]
                                     :separator \;
                                     :quote \'
                                     :quote? #(or (= "b" %) (str/includes? % ";"))
                                     :newline :cr+lf)
        pipe-output    (write-output [["left" "right"]] :separator \| :quote \')]
    [[:default-output default-output]
     [:default-roundtrip (read-all default-output)]
     [:custom-output custom-output]
     [:custom-roundtrip (read-all custom-output :separator \; :quote \')]
     [:read-csv-from-default (read-from "a,b\nc,d" \, \")]
     [:read-csv-from-custom (read-from (string-reader "a;b\n'c;d';e") \; \')]
     [:char-options-roundtrip (read-all pipe-output :separator \| :quote \')]
     [:invalid-options [(error? #(write-output [["x"]] :separator "::"))
                        (error? #(write-output [["x"]] :quote ""))
                        (write-output [["x"]] :newline :unknown)]]
     [:quote-controls [(write-output [["has,comma" "has\"quote" "plain"]]
                                     :quote? (constantly false))
                       (write-output [["a" "b"] ["" "c"]]
                                     :quote? (constantly true))]]]))

(defn scalar-summary []
  (let [rows [[nil true false 42 :kw 'sym]
              []
              ["leading" "" "trailing"]
              ["line\rbreak" "line\nbreak" "both\r\nbreak"]]
        default-output (write-output rows)
        custom-output  (write-output rows :separator \; :quote \')]
    [[:default-output default-output]
     [:default-roundtrip (read-all default-output)]
     [:custom-output custom-output]
     [:custom-roundtrip (read-all custom-output :separator \; :quote \')]]))

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(defn seeded-value [seed]
  (case (mod seed 8)
    0 (str "v" (mod seed 100000))
    1 (str "comma," (mod seed 100000))
    2 (str "quote\"" (mod seed 100000))
    3 (str "line\n" (mod seed 100000))
    4 (str "cr\r" (mod seed 100000))
    5 (str "both\r\n" (mod seed 100000))
    6 (str "semi;" (mod seed 100000))
    7 ""))

(defn generated-rows []
  (loop [remaining 96
         seed 326700001
         rows []]
    (if (zero? remaining)
      rows
      (let [s1 (next-seed seed)
            s2 (next-seed s1)
            s3 (next-seed s2)
            s4 (next-seed s3)]
        (recur (dec remaining)
               s4
               (conj rows [(seeded-value s1)
                           (seeded-value s2)
                           (seeded-value s3)
                           (seeded-value s4)]))))))

(defn generated-summary []
  (let [rows           (generated-rows)
        default-output (write-output rows)
        custom-output  (write-output rows :separator \; :quote \')]
    [[:row-count (count rows)]
     [:default-size (count default-output)]
     [:custom-size (count custom-output)]
     [:default-roundtrip (read-all default-output)]
     [:custom-roundtrip (read-all custom-output :separator \; :quote \')]]))
