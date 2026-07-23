;; Portable clojure.core.reducers/basilisp.reducers cases. These distinguish
;; bare map reduction from reducer/folder transformations over maps because
;; Clojure uses key/value arity for the former and entry values for serial
;; transformed reduction.

(require '[clojure.core.reducers :as r])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(def sorted-pairs
  (sorted-map :a 1 :b 2))

(emit-case :basic-transformations
           {:surface (every? #(contains? (ns-publics #?(:clj 'clojure.core.reducers
                                                        :lpy 'basilisp.core.reducers))
                                         %)
                             '[->Cat CollFold append! cat coll-fold drop filter
                               fjtask flatten fold foldcat folder map mapcat
                               monoid pool reduce reducer remove take take-while])
            :map (into [] (r/map inc [1 2 3]))
            :filter (into [] (r/filter even? [1 2 3 4]))
            :remove (into [] (r/remove even? [1 2 3 4]))
            :mapcat (into [] (r/mapcat #(vector % (inc %)) [1 2 3]))
            :flatten (into [] (r/flatten [1 [2 [3 4]]]))
            :take (into [] (r/take 3 [1 2 3 4 5]))
            :drop (into [] (r/drop 2 [1 2 3 4 5]))
            :take-while (into [] (r/take-while #(< % 4) [1 2 3 4 5]))})

(emit-case :map-reduction-boundary
           {:bare-map (r/reduce (fn [acc key value]
                                  (assoc acc key value))
                                {}
                                sorted-pairs)
            :mapped-entries (r/reduce (fn [acc entry]
                                        (conj acc [(key entry) (val entry)]))
                                      []
                                      (r/map identity sorted-pairs))
            :filtered-entries (r/reduce (fn [acc entry]
                                          (conj acc [(key entry) (val entry)]))
                                        []
                                        (r/filter #(= :b (key %)) sorted-pairs))
            :take-entry (r/reduce (fn [acc entry]
                                    (conj acc [(key entry) (val entry)]))
                                  []
                                  (r/take 1 sorted-pairs))})

(emit-case :fold-semantics
           {:sum (r/fold + [1 2 3 4])
            :partition-size (r/fold 2 + + [1 2 3 4])
            :map-key-values (r/fold (fn
                                      ([] {})
                                      ([left right] (merge left right)))
                                    (fn
                                      ([] {})
                                      ([acc key value] (assoc acc key value)))
                                    sorted-pairs)
            :mapped-key-values (r/fold (fn
                                         ([] [])
                                         ([left right] (into left right)))
                                       conj
                                       (r/map (fn [key value]
                                                [key (inc value)])
                                              sorted-pairs))
            :foldcat (vec (r/foldcat [[1 2] [3 4]]))})

(emit-case :early-reduced
           (let [calls (atom 0)
                 result (r/reduce (fn [acc value]
                                    (swap! calls inc)
                                    (if (= value 3)
                                      (reduced acc)
                                      (conj acc value)))
                                  []
                                  (r/mapcat #(vector % %) [1 2 3 4]))]
             {:result result
              :calls @calls}))

(emit-case :composition-stress
           (mapv (fn [size]
                   (let [values (range size)]
                     {:size size
                      :pipeline (into [] (r/take 7
                                                  (r/filter odd?
                                                            (r/map inc values))))
                      :cat-pipeline (into [] (r/take 9
                                                     (r/mapcat #(vector % (inc %))
                                                               values)))}))
                 (range 40)))

(emit-case :jvm-forkjoin-boundary
           (every? #(contains? (ns-publics #?(:clj 'clojure.core.reducers
                                              :lpy 'basilisp.core.reducers))
                               %)
                   '[pool fjtask]))
