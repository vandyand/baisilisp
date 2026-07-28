;; Portable clojure.data/basilisp.data cases. The namespace is small, but the
;; public protocol helpers are part of the Clojure surface and map diffs have a
;; distinct seq return shape, so this fixture locks both names and behavior.

(ns conformance.data-cases
  (:require [clojure.data :as data]))

(defrecord Pair [a b])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn result-shape [x]
  {:vector? (vector? x)
   :seq? (seq? x)
   :value x})

(emit-case :public-surface
           {:publics (sort (map name (keys (ns-publics #?(:clj 'clojure.data
                                                          :lpy 'basilisp.data)))))
            :protocol-vars [(some? data/Diff)
                            (some? data/EqualityPartition)]})

(emit-case :equality-partitions
           {:nil (data/equality-partition nil)
            :integer (data/equality-partition 1)
            :string (data/equality-partition "ab")
            :vector (data/equality-partition [1 2])
            :list (data/equality-partition '(1 2))
            :seq (data/equality-partition (seq [1 2]))
            :map (data/equality-partition {:a 1})
            :record (data/equality-partition (->Pair 1 2))
            :set (data/equality-partition #{1})})

(emit-case :basic-diffs
           {:equal (data/diff 1 1)
            :atom (data/diff 1 2)
            :string (data/diff "ab" "ac")
            :nil-left (data/diff nil {:a 1})
            :nil-right (data/diff {:a 1} nil)
            :set (data/diff #{1 2 3} #{2 3 4})
            :set-no-shared (data/diff #{1} #{2})})

(emit-case :sequential-diffs
           {:vector (data/diff [1 2 3] [1 4])
            :list (data/diff '(1 2 3) '(1 4))
            :seq-vs-vector (data/diff (seq [1 2]) [1 3])
            :nested (data/diff [{:a 1 :b 2} 2 #{1 2 3}]
                               [{:a 1 :b 3} 0 #{2 3 4} :extra])})

(emit-case :map-diffs-and-shapes
           {:map (result-shape (data/diff {:a 1 :b 2}
                                          {:a 1 :b 3 :c 4}))
            :diff-similar-map (result-shape (data/diff-similar {:a 1}
                                                               {:a 2}))
            :equal-map (result-shape (data/diff {:a 1} {:a 1}))
            :record (result-shape (data/diff (->Pair 1 2) (->Pair 1 3)))
            :sorted-map (result-shape (data/diff (sorted-map :a 1 :b 2)
                                                 (sorted-map :a 1 :b 3)))})

(emit-case :direct-protocol-methods
           {:atom (data/diff-similar 1 2)
            :vector (data/diff-similar [1 2] [1 3 4])
            :map (doall (data/diff-similar {:a 1} {:a 2}))
            :set (data/diff-similar #{1 2} #{2 3})})

(emit-case :nil-component-diffs
           {:map-left-nil (data/diff {:a nil} {:a 1})
            :map-right-nil (data/diff {:a 1} {:a nil})
            :map-shared-nil (data/diff {:a nil} {:a nil :b 1})
            :seq-shared-leading-nil (data/diff [nil 1] [nil 2])
            :seq-shared-trailing-nil (data/diff [1 nil] [2 nil])
            :seq-only-right-nil (data/diff [] [nil])
            :seq-only-left-nil (data/diff [nil] [])})

(emit-case :false-empty-and-metadata-diffs
           {:map-left-false (data/diff {:a false} {:a 1})
            :map-right-false (data/diff {:a 1} {:a false})
            :map-shared-false (data/diff {:a false :b 1} {:a false :b 2})
            :seq-shared-leading-false (data/diff [false 1] [false 2])
            :seq-shared-trailing-false (data/diff [1 false] [2 false])
            :empty-vector-shared (data/diff {:a [] :b 1} {:a [] :b 2})
            :empty-map-shared (data/diff {:a {} :b 1} {:a {} :b 2})
            :empty-set-shared (data/diff {:a #{} :b 1} {:a #{} :b 2})
            :metadata-ignored (let [[a b both] (data/diff ^{:left true} [1 2]
                                                          ^{:right true} [1 2])]
                                [a b both (meta both)])
            :metadata-left-retained (let [[_ _ both] (data/diff ^{:left true} {:a 1}
                                                                 ^{:right true} {:a 1})]
                                      (meta both))})

(emit-case :record-and-map-boundaries
           {:record-vs-record (result-shape (data/diff (->Pair 1 nil)
                                                       (->Pair 1 false)))
            :record-vs-map (result-shape (data/diff (->Pair 1 2)
                                                    {:a 1 :b 2}))
            :map-vs-record (result-shape (data/diff {:a 1 :b 2}
                                                    (->Pair 1 2)))
            :record-extra-map-key (result-shape (data/diff (->Pair 1 2)
                                                           {:a 1 :b 2 :c 3}))
            :sorted-map-vs-map (result-shape (data/diff (sorted-map :a 1 :b 2)
                                                        {:a 1 :b 3 :c 4}))
            :set-containing-empty-colls (data/diff #{[] {} #{}}
                                                   #{[] {:a 1} #{}})})

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(defn seeded-scalar [seed]
  (case (mod seed 6)
    0 (mod seed 97)
    1 (keyword (str "k" (mod seed 17)))
    2 (str "s" (mod seed 23))
    3 (zero? (mod seed 2))
    4 nil
    5 (symbol (str "sym" (mod seed 19)))))

(defn seeded-value [seed]
  (let [s1 (next-seed seed)
        s2 (next-seed s1)
        s3 (next-seed s2)]
    (case (mod seed 5)
      0 (seeded-scalar s1)
      1 [(seeded-scalar s1) (seeded-scalar s2)]
      2 {:a (seeded-scalar s1) :b (seeded-scalar s2)}
      3 (set [(seeded-scalar s1) (seeded-scalar s2) (seeded-scalar s3)])
      4 [{:x (seeded-scalar s1)} (set [(seeded-scalar s2)])])))

(defn seeded-deep-value [seed depth]
  (if (zero? depth)
    (seeded-scalar seed)
    (let [s1 (next-seed seed)
          s2 (next-seed s1)
          s3 (next-seed s2)
          s4 (next-seed s3)]
      (case (mod seed 8)
        0 (seeded-scalar s1)
        1 []
        2 {}
        3 #{}
        4 [(seeded-deep-value s1 (dec depth))
           (seeded-deep-value s2 (dec depth))
           (seeded-deep-value s3 (dec depth))]
        5 {:a (seeded-deep-value s1 (dec depth))
           :b (seeded-deep-value s2 (dec depth))
           :empty (case (mod s3 3) 0 [] 1 {} #{})}
        6 (set [(seeded-scalar s1)
                (seeded-scalar s2)
                (seeded-scalar s3)])
        7 [{:x (seeded-deep-value s1 (dec depth))}
           (set [(seeded-scalar s2)])
           (seeded-deep-value s4 (dec depth))]))))

(emit-case :seeded-structural-fuzz
           (loop [remaining 72
                  seed 195948557
                  result []]
             (if (zero? remaining)
               result
               (let [s1 (next-seed seed)
                     s2 (next-seed s1)
                     s3 (next-seed s2)
                     a {:left (seeded-value s1)
                        :shared (seeded-value s2)
                        :nested [(seeded-value s1) (seeded-value s2)]}
                     b {:right (seeded-value s3)
                        :shared (seeded-value s2)
                        :nested [(seeded-value s1) (seeded-value s3)]}
                     [only-a only-b both] (data/diff a b)]
                 (recur (dec remaining)
                        s3
                        (conj result {:only-a? (some? only-a)
                                      :only-b? (some? only-b)
                                      :shared (= (:shared both) (:shared a))
                                      :nested-shared (= (get-in both [:nested 0])
                                                        (get-in a [:nested 0]))}))))))

(emit-case :seeded-deep-structural-fuzz
           (loop [remaining 96
                  seed 981273
                  result []]
             (if (zero? remaining)
               result
               (let [s1 (next-seed seed)
                     s2 (next-seed s1)
                     s3 (next-seed s2)
                     shared (seeded-deep-value s1 4)
                     left (seeded-deep-value s2 4)
                     right (seeded-deep-value s3 4)
                     a {:shared shared
                        :left left
                        :empty []
                        :nested [{:shared shared} left false nil]}
                     b {:shared shared
                        :right right
                        :empty []
                        :nested [{:shared shared} right false nil]}
                     [only-a only-b both] (data/diff a b)
                     [same-a same-b same-both] (data/diff a a)]
                 (recur (dec remaining)
                        s3
                        (conj result
                              {:same-a? (nil? same-a)
                               :same-b? (nil? same-b)
                               :same-both? (= same-both a)
                               :only-a? (some? only-a)
                               :only-b? (some? only-b)
                               :shared (= (:shared both) shared)
                               :empty (= (:empty both) [])
                               :nested-shared (= (get-in both [:nested 0 :shared])
                                                 shared)
                               :nested-false (= (get-in both [:nested 2])
                                                false)
                               :nested-nil (= (get-in both [:nested 3])
                                              nil)}))))))
