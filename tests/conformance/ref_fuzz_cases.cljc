;; A deterministic pseudo-random Ref corpus. It is intentionally data-only so
;; the differential runner can compare this exact workload in Clojure and
;; Basilisp without relying on host thread scheduling or exception classes.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(defn delta [seed]
  (- (mod seed 17) 8))

(let [value (ref 0)
      summary (loop [seed 424242
                     expected 0
                     checksum 0
                     remaining 256]
                (if (zero? remaining)
                  {:value @value :checksum checksum}
                  (let [next (next-seed seed)
                        change (delta next)
                        expected-next (+ expected change)
                        operation (mod next 4)]
                    (dosync
                     (ensure value)
                     (case operation
                       0 (alter value + change)
                       1 (ref-set value expected-next)
                       2 (commute value + change)
                       3 (dosync (alter value + change))))
                    (let [actual @value]
                      (when (not= expected-next actual)
                        (throw (ex-info "Ref fuzz model diverged"
                                        {:expected expected-next
                                         :actual actual
                                         :operation operation})))
                      (recur next
                             expected-next
                             (mod (+ (* checksum 31) actual) 2147483647)
                             (dec remaining))))))]
  (emit-case :ref-deterministic-fuzz summary))

(let [guard (ref 0 :validator even?)
      aborted (loop [remaining 64
                     aborted 0]
                (if (zero? remaining)
                  aborted
                  (let [before @guard
                        failed? (try
                                  (dosync (alter guard inc))
                                  false
                                  (catch Exception _ true))]
                    (when (or (not failed?) (not= before @guard))
                      (throw (ex-info "Ref validator fuzz escaped its transaction"
                                      {:before before :after @guard})))
                    (recur (dec remaining) (inc aborted)))))]
  (emit-case :ref-validator-aborts {:aborted aborted :value @guard}))
