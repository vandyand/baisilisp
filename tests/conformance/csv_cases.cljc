;; Portable clojure.data.csv/basilisp.data.csv cases. Clojure data.csv is not
;; bundled with Clojure itself, so this fixture is run with an explicit
;; org.clojure/data.csv dependency on the Clojure side. It compares public
;; surface, read-csv/read-csv-from behavior, write-csv options, quote escaping,
;; and seeded round trips.

#?(:clj (require '[clojure.data.csv :as csv]
                 '[clojure.string :as str])
   :lpy (require '[clojure.data.csv :as csv]
                 '[basilisp.string :as str]))

#?(:clj (import [java.io StringReader StringWriter])
   :lpy (import io))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn public-csv-names []
  (sort (map name (keys (ns-publics #?(:clj 'clojure.data.csv
                                        :lpy 'basilisp.data.csv))))))

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

(emit-case :public-surface
           (public-csv-names))

(emit-case :basic-reading
           {:string (read-all "id,name\n1,Ada\n2,Rich")
            :reader (read-all (string-reader "a,b\nc,d"))
            :empty-string (read-all "")
            :empty-reader (read-all (string-reader ""))})

(emit-case :read-csv-from
           {:default (vec (csv/read-csv-from "a,b\nc,d" (int \,) (int \")))
            :custom (vec (csv/read-csv-from (string-reader "a;b\n'c;d';e")
                                            (int \;)
                                            (int \')))})

(emit-case :writing-options
           {:default (write-output [["a" "b"] ["has,comma" "has\"quote"]])
            :custom (write-output [["a" "b"] ["c;d" "e"]]
                                  :separator \;
                                  :quote \'
                                  :quote? #(= "b" %)
                                  :newline :cr+lf)})

(emit-case :quoted-reading
           (read-all "\"a,b\",\"has\"\"quote\",\"has\nnewline\"\r\nplain,last,end"))

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(defn seeded-value [seed]
  (case (mod seed 6)
    0 (str "v" (mod seed 100000))
    1 (str "comma," (mod seed 100000))
    2 (str "quote\"" (mod seed 100000))
    3 (str "line\n" (mod seed 100000))
    4 (str "semi;" (mod seed 100000))
    5 ""))

(emit-case :seeded-round-trips
           (loop [remaining 36
                  seed 326700001
                  rows []]
             (if (zero? remaining)
               (let [csv-text (write-output rows)]
                 {:rows rows
                  :round-trip (read-all csv-text)
                  :custom-round-trip (read-all
                                      (write-output rows :separator \; :quote \')
                                      :separator \;
                                      :quote \')})
               (let [s1 (next-seed seed)
                     s2 (next-seed s1)
                     s3 (next-seed s2)]
                 (recur (dec remaining)
                        s3
                        (conj rows [(seeded-value s1)
                                    (seeded-value s2)
                                    (seeded-value s3)]))))))
