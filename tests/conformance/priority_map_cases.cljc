;; Public priority-map behaviour rendered as plain EDN data for both runtimes.

(require '[clojure.data.priority-map :as pm])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(let [p (pm/priority-map :a 2 :b 1 :c 3)]
  (emit-case :queue {:entries (vec p)
                     :peek (peek p)
                     :pop (vec (pop p))
                     :reassigned (vec (assoc p :a 0))}))

(emit-case :keyfn-and-comparator
           {:descending (vec (pm/priority-map-by > :a 1 :b 3 :c 2))
            :keyfn (vec (pm/priority-map-keyfn first :a [2 :apple] :b [1 :banana]))})

(let [p (pm/priority-map :a 2 :b 1 :c 3)]
  (emit-case :bounds {:subseq (vec (pm/subseq p < 3))
                      :rsubseq (vec (pm/rsubseq p >= 2))
                      :groups (pm/priority->set-of-items (assoc p :d 2))}))
