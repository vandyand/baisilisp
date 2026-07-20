#?(:clj (load-file "tests/acceptance/upstream/medley/upstream/src/medley/core.cljc")
   :lpy (require '[medley.core]))
(alias 'm 'medley.core)

(println
 (pr-str
  {:find (m/find-first even? [1 3 4 6])
   :dissoc (m/dissoc-in {:a {:b {:c 1 :d 2}}} [:a :b :c])
   :assoc (m/assoc-some {:a 1} :b 2 :c nil :d 3)
   :maps [(m/map-keys name {:a 1 :b 2})
          (m/map-vals inc {:a 1 :b 2})
          (m/filter-vals even? {:a 1 :b 2 :c 4})
          (m/map-kv-keys (fn [k v] (str (name k) v)) {:a 1 :b 2})
          (m/map-kv-vals (fn [k v] (str (name k) v)) {:a 1 :b 2})]
   :order [(m/least 3 2 5 -1 0) (m/greatest 3 2 5 -1 0)
           (m/least-by :n {:n 3} {:n 1} {:n 2})
           (m/greatest-by :n {:n 3} {:n 1} {:n 2})]
   :deep (m/deep-merge {:a {:b 1 :c 2}} {:a {:b 2 :d 3}})
   :collate [(m/collate-by even? + [1 2 3 4 5])
             (m/index-by first [[:a 1] [:b 2] [:a 3]])]
   :queue [(m/queue? (m/queue [1 2])) (vec (m/queue [1 2]))]
   :interleave (vec (m/interleave-all [1 2] [:a :b :c] [:x]))
   :distinct (vec (m/distinct-by first [[:a 1] [:a 2] [:b 3] [:a 4]]))
   :take-drop [(vec (m/take-upto #(= % 3) [1 2 3 4]))
               (vec (m/drop-upto #(= % 3) [1 2 3 4]))]
   :partition (mapv vec (m/partition-between #(= %2 3) [1 2 3 4 5]))
   :partition-edges [(mapv vec (m/partition-after even? [1 2 3 4 5]))
                     (mapv vec (m/partition-before even? [1 2 3 4 5]))]
   :window (mapv vec (m/window 3 [1 2 3 4]))
   :indexed (vec (m/indexed [:a :b :c]))
   :edits [(vec (m/insert-nth 2 :x [1 2 3]))
           (vec (m/remove-nth 1 [1 2 3]))
           (vec (m/replace-nth 1 :x [1 2 3]))]
   :index (m/index-of [1 2 3 2] 2)
   :atoms (let [a (atom 1)]
            [(m/deref-swap! a + 2) @a (m/deref-reset! a 9) @a])
   :transducers [(into [] (m/find-first even?) [1 3 4 6])
                 (into [] (m/take-upto #(= % 3)) [1 2 3 4])
                 (into [] (m/drop-upto #(= % 3)) [1 2 3 4])
                 (into [] (m/partition-between #(= %2 3)) [1 2 3 4 5])]
   :host [(m/boolean? true) (m/boolean? 1) (m/abs -3)
          (m/regexp? #"a+")
          (m/uuid? (m/uuid "123e4567-e89b-12d3-a456-426614174000"))]}))
