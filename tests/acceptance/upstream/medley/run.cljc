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
          (m/filter-vals even? {:a 1 :b 2 :c 4})]
   :order [(m/least 3 2 5 -1 0) (m/greatest 3 2 5 -1 0)]
   :deep (m/deep-merge {:a {:b 1 :c 2}} {:a {:b 2 :d 3}})
   :interleave (vec (m/interleave-all [1 2] [:a :b :c] [:x]))
   :distinct (vec (m/distinct-by first [[:a 1] [:a 2] [:b 3] [:a 4]]))
   :take-drop [(vec (m/take-upto #(= % 3) [1 2 3 4]))
               (vec (m/drop-upto #(= % 3) [1 2 3 4]))]
   :partition (mapv vec (m/partition-between #(= %2 3) [1 2 3 4 5]))
   :window (mapv vec (m/window 3 [1 2 3 4]))
   :edits [(vec (m/insert-nth 2 :x [1 2 3]))
           (vec (m/remove-nth 1 [1 2 3]))
           (vec (m/replace-nth 1 :x [1 2 3]))]
   :index (m/index-of [1 2 3 2] 2)}))
