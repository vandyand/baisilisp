;; Portable clojure.zip/basilisp.zip conformance cases. The fixture compares
;; pure data summaries rather than location metadata, whose function values are
;; host objects.

(require '[clojure.zip :as zip])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(def sample-tree [[:a :b] :c [:d [:e :f]]])

(defn nodes-in-order [loc]
  (loop [loc loc
         nodes []]
    (if (zip/end? loc)
      nodes
      (recur (zip/next loc) (conj nodes (zip/node loc))))))

(defn last-loc [loc]
  (loop [loc loc]
    (let [next-loc (zip/next loc)]
      (if (zip/end? next-loc)
        loc
        (recur next-loc)))))

(defn nodes-in-reverse-order [loc]
  (loop [loc loc
         nodes []]
    (if loc
      (recur (zip/prev loc) (conj nodes (zip/node loc)))
      nodes)))

(defn thrown?* [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn generated-tree [depth seed]
  (if (zero? depth)
    seed
    (case (mod (+ seed depth) 4)
      0 seed
      1 [(generated-tree (dec depth) (+ seed 1))]
      2 [(generated-tree (dec depth) (+ seed 1))
         (generated-tree (dec depth) (+ seed 3))]
      [(generated-tree (dec depth) (+ seed 1))
       [(generated-tree (dec depth) (+ seed 3))
        (generated-tree (dec depth) (+ seed 5))]])))

(defn map-leaves [node f]
  (if (vector? node)
    (mapv #(map-leaves % f) node)
    (f node)))

(defn remove-leaves [node pred]
  (if (vector? node)
    (vec (keep (fn [child]
                 (when (or (vector? child) (not (pred child)))
                   (remove-leaves child pred)))
               node))
    node))

(defn replace-leaves-through-zip [tree f]
  (loop [loc (zip/vector-zip tree)]
    (if (zip/end? loc)
      (zip/root loc)
      (recur (zip/next (if (zip/branch? loc)
                         loc
                         (zip/edit loc f)))))))

(defn remove-leaves-through-zip [tree pred]
  (loop [loc (zip/vector-zip tree)]
    (if (zip/end? loc)
      (zip/root loc)
      (recur (zip/next (if (and (not (zip/branch? loc))
                                (pred (zip/node loc)))
                         (zip/remove loc)
                         loc))))))

(emit-case :public-surface
           (sort (map name (keys (ns-publics #?(:clj 'clojure.zip
                                                :lpy 'basilisp.zip))))))

(emit-case :navigation
           (let [root-loc (zip/vector-zip sample-tree)
                 first-child (zip/down root-loc)
                 middle-child (zip/right first-child)
                 final-child (zip/right middle-child)
                 nested-child (zip/down final-child)
                 traversal (nodes-in-order root-loc)
                 last-node (last-loc root-loc)]
             {:root (zip/node root-loc)
              :children (vec (zip/children root-loc))
              :path (zip/path first-child)
              :lefts (zip/lefts middle-child)
              :rights (zip/rights first-child)
              :leftmost (zip/node (zip/leftmost final-child))
              :rightmost (zip/node (zip/rightmost first-child))
              :up (zip/node (zip/up nested-child))
              :traversal traversal
              :reverse (nodes-in-reverse-order last-node)
              :end-root (zip/root (loop [loc root-loc]
                                    (if (zip/end? loc)
                                      loc
                                      (recur (zip/next loc)))))}))

(emit-case :editing
           (let [root-loc (zip/vector-zip sample-tree)
                 middle-child (-> root-loc zip/down zip/right)]
             {:replace (zip/root (zip/replace middle-child :C))
              :edit (zip/root (zip/edit middle-child name))
              :insert-left (zip/root (zip/insert-left middle-child :before))
              :insert-right (zip/root (zip/insert-right middle-child :after))
              :insert-child (zip/root (zip/insert-child root-loc :first))
              :append-child (zip/root (zip/append-child root-loc :last))
              :remove-middle (zip/root (zip/remove middle-child))
              :remove-first (zip/root (zip/remove (zip/down root-loc)))}))

(emit-case :seq-zip-and-custom-boundaries
           (let [seq-tree (with-meta '((:a :b) :c) {:tag :seq-root})
                 seq-result (-> (zip/seq-zip seq-tree)
                                zip/down
                                zip/right
                                (zip/replace :C)
                                zip/root)
                 custom-root {:value :root :children [{:value :leaf}]}
                 custom-loc (zip/zipper map?
                                        :children
                                        (fn [node children]
                                          (assoc node :children (vec children)))
                                        custom-root)]
             {:seq-root seq-result
              :seq-root-meta (meta seq-result)
              :seq-singleton-remove-errors
              [(thrown?* #(-> (zip/seq-zip '(:only)) zip/down zip/remove zip/root))
               (thrown?* #(-> (zip/seq-zip (with-meta '(:only) {:tag :seq-root}))
                              zip/down zip/remove zip/root))]
              :custom-root (zip/root (zip/append-child custom-loc {:value :added}))
              :custom-child (zip/node (zip/down custom-loc))}))

(emit-case :generated-traversal-edit-removal-corpus
           (mapv (fn [seed]
                   (let [tree (generated-tree 5 seed)
                         tree (if (vector? tree) tree [tree])
                         ordered (nodes-in-order (zip/vector-zip tree))
                         last-node (last-loc (zip/vector-zip tree))]
                     {:seed seed
                      :count (count ordered)
                      :first (first ordered)
                      :last (last ordered)
                      :reverse-ok (= (reverse ordered)
                                     (nodes-in-reverse-order last-node))
                      :edit-ok (= (map-leaves tree inc)
                                  (replace-leaves-through-zip tree inc))
                      :remove-ok (= (remove-leaves tree #(zero? (mod % 3)))
                                    (remove-leaves-through-zip tree #(zero? (mod % 3))))}))
                 (range 32)))
