;; Portable clojure.set/basilisp.set conformance cases. These lock the
;; Clojure-required public contract and semantic edge cases while allowing
;; Basilisp's documented extension helpers to remain extra public Vars.

(require '[clojure.set :as set])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(def required-publics
  ["difference"
   "index"
   "intersection"
   "join"
   "map-invert"
   "project"
   "rename"
   "rename-keys"
   "select"
   "subset?"
   "superset?"
   "union"])

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn generated-set [seed offset]
  (into (sorted-set)
        (map #(mod (+ (* seed 17) (* % 7) offset) 29))
        (range (mod (+ seed offset) 11))))

(defn generated-hash-set [seed offset]
  (set (map #(mod (+ (* seed 13) (* % 5) offset) 31)
            (range (mod (+ seed offset) 13)))))

(defn sorted-vec [xs]
  (vec (sort xs)))

(defn generated-relation [seed side]
  (set
   (map (fn [idx]
          {:id (mod (+ seed idx) 5)
           :group (mod (+ seed (* idx 2)) 3)
           :side side
           :value (+ (* seed 10) idx)})
        (range (mod (+ seed side) 7)))))

(emit-case :public-surface
           (let [publics (set (map name (keys (ns-publics #?(:clj 'clojure.set
                                                             :lpy 'basilisp.set)))))]
             {:required-present (mapv #(contains? publics %) required-publics)}))

(emit-case :arity-and-basic-operations
           {:union-zero (set/union)
            :intersection-zero-rejected (rejected? #(set/intersection))
            :difference-zero-rejected (rejected? #(set/difference))
            :union (set/union #{1 2} #{2 3} #{3 4})
            :intersection (set/intersection #{1 2 3 4} #{2 3 5} #{0 2 3})
            :difference (set/difference #{1 2 3 4} #{2 5} #{4})
            :subset? [(set/subset? #{1 2} #{1 2 3})
                      (set/subset? #{1 4} #{1 2 3})]
            :superset? [(set/superset? #{1 2 3} #{1 2})
                        (set/superset? #{1 2} #{1 2 3})]})

(emit-case :metadata-and-sorted-preservation
           (let [sorted-source (with-meta (sorted-set 3 1 2) {:m :sorted})
                 small-sorted (with-meta (sorted-set 1) {:m :small})
                 large-hash (with-meta #{1 2 3} {:m :large})]
             {:union-sorted-meta (meta (set/union sorted-source #{4}))
              :union-sorted? (sorted? (set/union sorted-source #{4}))
              :union-seq (vec (set/union sorted-source #{4}))
              :intersection-sorted-meta (meta (set/intersection sorted-source #{2 3 4}))
              :intersection-sorted? (sorted? (set/intersection sorted-source #{2 3 4}))
              :intersection-seq (vec (set/intersection sorted-source #{2 3 4}))
              :difference-sorted-meta (meta (set/difference sorted-source #{3}))
              :difference-sorted? (sorted? (set/difference sorted-source #{3}))
              :difference-seq (vec (set/difference sorted-source #{3}))
              :select-sorted-meta (meta (set/select odd? sorted-source))
              :select-sorted? (sorted? (set/select odd? sorted-source))
              :select-seq (vec (set/select odd? sorted-source))
              :union-large-source-meta (meta (set/union small-sorted large-hash))
              :union-large-source-sorted? (sorted? (set/union small-sorted large-hash))
              :intersection-small-source-meta (meta (set/intersection large-hash small-sorted))
              :intersection-small-source-sorted? (sorted? (set/intersection large-hash small-sorted))}))

(emit-case :relational-helpers
           (let [rel #{{:id 1 :group :a :name "Ada"}
                       {:id 2 :group :a :name "Alan"}
                       {:id 3 :group :b :name "Grace"}}
                 ranked-left (sorted-set-by #(compare (:left-rank %1) (:left-rank %2))
                                            {:left-rank 0 :rank 0 :id 1 :left :first}
                                            {:left-rank 1 :region :east :left :second})
                 ranked-right (sorted-set-by #(compare (:right-rank %1) (:right-rank %2))
                                             {:right-rank 0 :rank 0 :id 1 :right :first}
                                             {:right-rank 1 :id 99 :region :east :right :second})]
             {:index (set/index rel [:group])
              :project (set/project rel [:id :group])
              :rename-keys (set/rename-keys {:id 1 :name "Ada"} {:id :person/id})
              :rename (set/rename rel {:id :person/id})
              :map-invert (set/map-invert {:a 1 :b 2})
              :natural-join (set/join #{{:id 1 :name "Ada"} {:id 2 :name "Alan"}}
                                      #{{:id 1 :lang :lisp} {:id 3 :lang :python}})
              :keymap-join (set/join #{{:id 1 :name "Ada"} {:id 2 :name "Alan"}}
                                     #{{:person/id 1 :lang :lisp}
                                       {:person/id 3 :lang :python}}
                                     {:id :person/id})
              :empty-joins [(set/join #{} #{{:id 1}})
                            (set/join #{{:id 1}} #{})
                            (set/join #{} #{})]
              :first-row-shared-keys (set/join ranked-left ranked-right)}))

(emit-case :generated-corpus
           (mapv (fn [seed]
                   (let [a (generated-set seed 0)
                         b (generated-hash-set seed 1)
                         c (generated-set seed 2)
                         rel-a (generated-relation seed 0)
                         rel-b (generated-relation seed 1)]
                     {:seed seed
                      :union (sorted-vec (set/union a b c))
                      :intersection (sorted-vec (set/intersection a b c))
                      :difference (sorted-vec (set/difference a b c))
                      :select (sorted-vec (set/select odd? a))
                      :subset-superset [(set/subset? (set/intersection a b) a)
                                        (set/superset? (set/union a b) a)]
                      :join-count (count (set/join rel-a rel-b))
                      :project-count (count (set/project rel-a [:id :group]))}))
                 (range 64)))
