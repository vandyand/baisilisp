;; Ref history controls have deterministic public behavior independent of the
;; JVM's internal transaction scheduling. Keep this corpus data-only so the
;; differential harness can compare Clojure and Basilisp exactly.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(let [value (ref 0)]
  (ref-min-history value 3)
  (ref-max-history value 5)
  (doseq [n (range 1 7)]
    (dosync (ref-set value n)))
  (emit-case :configured-history
             {:value @value
              :count (ref-history-count value)
              :minimum (ref-min-history value)
              :maximum (ref-max-history value)})
  (ref-min-history value 0)
  (ref-max-history value 1)
  (dosync (ref-set value 7))
  (emit-case :lowered-controls-retain-existing-history
             {:count (ref-history-count value)
              :minimum (ref-min-history value)
              :maximum (ref-max-history value)}))

(let [value (ref 0)]
  (ref-min-history value 1.9)
  (ref-max-history value -1.9)
  (emit-case :numeric-control-coercion
             [(ref-min-history value) (ref-max-history value)]))

(let [value (ref 0)
      summary (loop [seed 2463534242
                     expected 0
                     remaining 192]
                (if (zero? remaining)
                  {:value @value
                   :count (ref-history-count value)
                   :minimum (ref-min-history value)
                   :maximum (ref-max-history value)}
                  (let [next (mod (+ (* seed 1664525) 1013904223) 4294967296)
                        mode (mod next 5)
                        n (- (mod next 13) 4)]
                    (case mode
                      0 (ref-min-history value n)
                      1 (ref-max-history value n)
                      2 (dosync (alter value + n))
                      3 (dosync (ref-set value (+ expected n)))
                      4 (dosync (commute value + n)))
                    (recur next
                           (if (< mode 2) expected (+ expected n))
                           (dec remaining)))))]
  (emit-case :history-control-fuzz summary))
