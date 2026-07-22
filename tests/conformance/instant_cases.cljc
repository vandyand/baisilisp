;; Portable clojure.instant/basilisp.instant timestamp grammar and #inst reader
;; cases. Reader comparisons use inst-ms because Clojure returns java.util.Date
;; while Basilisp returns Python datetime.datetime.

#?(:clj (require '[clojure.instant :as instant])
   :lpy (require '[basilisp.instant :as instant]))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn errors? [f]
  (try
    (f)
    false
    (catch Exception _ true)))

(def timestamp-inputs
  ["2024"
   "2024-02"
   "2024-02-03"
   "2024-02-03T04"
   "2024-02-03T04:05"
   "2024-02-03T04:05:06"
   "2024-02-03T04:05:06.7"
   "2024-02-03T04:05:06.123456789123Z"
   "2024-02-03T04:05:06.7-07:30"
   "2024-02-03T04:05:06+02:15"
   "2024-99"
   "2024-01-01T00:00:60Z"])

(emit-case :parse-timestamp-components
           (mapv #(instant/parse-timestamp vector %) timestamp-inputs))

(emit-case :parse-timestamp-malformed
           (mapv #(errors? (fn [] (instant/parse-timestamp vector %)))
                 [nil
                  ""
                  "2024-1"
                  "2024-01-01T"
                  "2024-01-01T00:"
                  "2024-01-01T00:00:"
                  "not an instant"]))

(def reader-inputs
  ["#inst \"2024\""
   "#inst \"2024-02\""
   "#inst \"2024-02-03\""
   "#inst \"2024-02-03T04\""
   "#inst \"2024-02-03T04:05\""
   "#inst \"2024-02-03T04:05:06\""
   "#inst \"2024-02-03T04:05:06.123456789123Z\""
   "#inst \"2024-02-03T04:05:06.7-07:30\""
   "#inst \"2024-02-03T04:05:06+02:15\""])

(emit-case :reader-inst-ms
           (mapv #(inst-ms (read-string %)) reader-inputs))

(emit-case :reader-invalid-calendar
           (mapv #(errors? (fn [] (read-string %)))
                 ["#inst \"2024-99\""
                  "#inst \"2023-02-29\""
                  "#inst \"2024-01-01T00:00:60Z\""
                  "#inst \"not an instant\""]))

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(defn pad2 [n]
  (let [s (str n)]
    (if (= 1 (count s)) (str "0" s) s)))

(emit-case :seeded-reader-corpus
           (loop [remaining 48
                  seed 314159
                  result []]
             (if (zero? remaining)
               result
               (let [s1 (next-seed seed)
                     s2 (next-seed s1)
                     s3 (next-seed s2)
                     s4 (next-seed s3)
                     s5 (next-seed s4)
                     s6 (next-seed s5)
                     year (+ 1970 (mod s1 80))
                     month (inc (mod s2 12))
                     day (inc (mod s3 28))
                     hour (mod s4 24)
                     minute (mod s5 60)
                     second (mod s6 60)
                     source (str "#inst \"" year "-"
                                 (pad2 month) "-"
                                 (pad2 day) "T"
                                 (pad2 hour) ":"
                                 (pad2 minute) ":"
                                 (pad2 second) "Z\"")]
                 (recur (dec remaining)
                        s6
                        (conj result (inst-ms (read-string source))))))))
