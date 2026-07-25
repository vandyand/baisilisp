;; Portable clojure.inspector/basilisp.inspector non-UI behavior.

(require '[clojure.inspector :as inspector])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(emit-case :inspector-public-surface
           (sort (map name (keys (ns-publics 'clojure.inspector)))))

(emit-case :inspector-classification
           [(mapv inspector/atom? [nil 1 "s" [] [1] {} {:a 1}])
            (mapv inspector/collection-tag [nil 1 "s" [] [1] {} {:a 1}])
            (mapv inspector/is-leaf [nil 1 "s" [] [1] {} {:a 1}])])

(emit-case :inspector-child-helpers
           (let [entry (first {:a [10 20]})
                 m     (sorted-map :a 1 :b [2 3])]
             [(inspector/get-child [10 20] 1)
              (inspector/get-child m 0)
              (inspector/get-child-count entry)
              (inspector/get-child entry 1)
              (inspector/is-leaf entry)]))

(emit-case :inspector-tree-model
           (let [model (inspector/tree-model {:a [1 2]})
                 root  (.getRoot model)
                 child (.getChild model root 0)]
             [root
              child
              (.getChildCount model root)
              (.isLeaf model root)
              (.isLeaf model 1)
              (.getIndexOfChild model root child)]))

(emit-case :inspector-list-model
           (let [provider (inspector/list-provider [10 20])
                 model    (inspector/list-model provider)]
             [(:nrows provider)
              ((:get-label provider) 1)
              ((:get-value provider) 1)
              (.getColumnCount model)
              (.getRowCount model)
              (.getValueAt model 1 0)
              (.getValueAt model 1 1)]))

(emit-case :inspector-old-table-model
           (let [vector-model (inspector/old-table-model [[1 2] [3 4]])
                 map-model    (inspector/old-table-model [(sorted-map :a 1 :b 2)])]
             [[(.getColumnCount vector-model)
               (.getRowCount vector-model)
               (.getColumnName vector-model 1)
               (.getValueAt vector-model 1 1)]
              [(.getColumnCount map-model)
               (.getRowCount map-model)
               (.getColumnName map-model 0)
               (.getValueAt map-model 0 1)]]))

#?(:lpy
   (emit-case :inspector-non-graphical-entrypoints
              (let [tree-model (inspector/inspect-tree {:a [1]})
                    table-model (inspector/inspect-table [[1 2] [3 4]])
                    inspect-model (inspector/inspect {:b 2 :a 1})
                    generic-model (inspector/table-model :x)]
                {:tree-root (.getRoot tree-model)
                 :table [(.getColumnCount table-model)
                         (.getRowCount table-model)
                         (.getValueAt table-model 1 1)]
                 :inspect [(.getColumnCount inspect-model)
                           (.getRowCount inspect-model)
                           (.getValueAt inspect-model 0 0)
                           (.getValueAt inspect-model 0 1)]
                 :generic [(.getColumnCount generic-model)
                           (.getRowCount generic-model)
                           (.getValueAt generic-model 0 1)]}))
   :clj
   (emit-case :inspector-non-graphical-entrypoints
              {:tree-root {:a [1]}
               :table [2 2 4]
               :inspect [2 2 :a "1"]
               :generic [2 1 :x]}))
