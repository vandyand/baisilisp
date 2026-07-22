;; Portable loop/recur closure-capture cases. These cases assert that each
;; closure created during a loop iteration keeps that iteration's local cells
;; after later recur assignments and after lazy realization outside the loop.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn invoke-all [fs]
  (mapv (fn [f] (f)) fs))

(emit-case :single-loop-local
           (loop [i 0
                  fs []]
             (if (< i 8)
               (recur (inc i)
                      (conj fs (fn [] i)))
               (invoke-all fs))))

(emit-case :multiple-loop-and-let-locals
           (loop [i 0
                  total 0
                  fs []]
             (if (< i 8)
               (let [square (* i i)
                     next-total (+ total i)]
                 (recur (inc i)
                        next-total
                        (conj fs (fn [] [i total square next-total]))))
               (invoke-all fs))))

(emit-case :nested-closures
           (loop [i 0
                  factories []]
             (if (< i 8)
               (let [offset (+ i 100)]
                 (recur (inc i)
                        (conj factories
                              (fn []
                                (fn []
                                  [i offset])))))
               (mapv (fn [factory] ((factory))) factories))))

(emit-case :lazy-realization-after-loop-exit
           (let [closures (doall
                           (loop [i 0
                                  lazy-items []]
                             (if (< i 8)
                               (let [captured (* i 10)]
                                 (recur (inc i)
                                        (conj lazy-items
                                              (lazy-seq [(fn [] [i captured])]))))
                               (mapcat identity lazy-items))))]
             (invoke-all closures)))

(emit-case :large-loop-no-recursion-growth
           (loop [i 0
                  total 0
                  samples []]
             (if (< i 512)
               (recur (inc i)
                      (+ total i)
                      (if (< i 10)
                        (conj samples (fn [] [i total]))
                        samples))
               {:total total
                :samples (invoke-all samples)})))

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(defn signed-value [seed]
  (- (mod seed 2001) 1000))

(emit-case :seeded-loop-closure-corpus
           (loop [i 0
                  seed 8675309
                  fs []
                  expected []]
             (if (< i 64)
               (let [next (next-seed seed)
                     value (signed-value next)
                     combined (+ value i)]
                 (recur (inc i)
                        next
                        (conj fs (fn [] [i value combined]))
                        (conj expected [i value combined])))
               {:expected expected
                :actual (invoke-all fs)})))
