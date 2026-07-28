;; Clojure-compatible merge/conj edge cases. These cases intentionally include
;; behavior Clojure's own tests label undefined, because applications sometimes
;; observe it and Basilisp can match it without host emulation.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn result
  [f]
  (try
    [:ok (f)]
    (catch Exception _
      [:err])))

(emit-case :ordinary-map-merge
           [(merge)
            (merge nil)
            (merge nil nil)
            (merge nil {:a 1})
            (merge {:a 1} nil {:a 2 :b nil})
            (merge {} [:foo "foo"])
            (merge {} {:a nil} [:a 1])])

(emit-case :permissive-first-argument-reduction
           [(merge [:foo])
            (merge :foo)
            (merge '(1 2 3) 1)
            (merge [1 2] 3 4 5)
            (merge [] nil {} 1 {:a :c})
            (merge (first {:a :a-val}) {:b :b-val} {:c :c-val})])

(emit-case :map-conj-entry-boundaries
              [(result #(conj {} [:a 1]))
               (result #(conj {} (first {:a 1})))
               (result #(conj {} nil))
               (result #(conj {} {}))
               (result #(conj {} {:a 1}))
               (result #(conj {} [[:a 1] [:b 2]]))
               (result #(conj {} '(:a 1)))
               (result #(conj {} (list [:a 1])))
               (result #(conj {} "ab"))
               (result #(conj {} [:a]))
               (result #(conj {} [:a 1 2]))
               (result #(merge {} '(:a 1)))
               (result #(merge {} (list [:a 1])))
               (result #(merge {} "ab"))
               (result #(merge {} [:a]))
               (result #(merge {} [:a 1 2]))])

(emit-case :merge-map-entry-boundaries
           [(result #(merge nil [:a 1]))
            (result #(merge nil (first {:a 1})))
            (result #(merge nil {}))
            (result #(merge nil {:a 1}))
            (result #(merge nil [[:a 1] [:b 2]]))
            (result #(merge [] [:a 1]))
            (result #(merge [:seed 0] [:a 1]))
            (result #(merge (first {:seed 0}) [:a 1]))
            (result #(merge {:a 0} nil [:a 1] {:b 2}))
            (result #(merge {:a 0} [[:a 1] [:b 2]]))
            (result #(merge {:a 0} (list [:a 1])))
            (result #(merge {:a 0} [:a]))
            (result #(merge {:a 0} [:a 1 2]))])

(defn transient-map-conj
  [& elems]
  (persistent! (reduce conj! (transient {}) elems)))

(emit-case :transient-map-conj-entry-boundaries
           [(result #(transient-map-conj [:a 1]))
            (result #(transient-map-conj (first {:a 1})))
            (result #(transient-map-conj nil))
            (result #(transient-map-conj {}))
            (result #(transient-map-conj {:a 1}))
            (result #(transient-map-conj [[:a 1] [:b 2]]))
            (result #(transient-map-conj '(:a 1)))
            (result #(transient-map-conj (list [:a 1])))
            (result #(transient-map-conj "ab"))
            (result #(transient-map-conj [:a]))
            (result #(transient-map-conj [:a 1 2]))
            (result #(transient-map-conj {:a 0} [:a 1] {:b 2}))])

(defn next-merge-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(emit-case :seeded-vector-merge-corpus
           (loop [remaining 48
                  seed 809301
                  result []]
             (if (zero? remaining)
               result
               (let [s1 (next-merge-seed seed)
                     s2 (next-merge-seed s1)
                     s3 (next-merge-seed s2)
                     k1 (keyword (str "k" (mod s1 13)))
                     k2 (keyword (str "k" (mod s2 13)))
                     v1 (mod s2 97)
                     v2 (mod s3 97)
                     first-arg (case (mod s1 4)
                                 0 {}
                                 1 []
                                 2 [k1 v1]
                                 (first {k1 v1}))
                     merged (merge first-arg {k1 :overwritten} [k2 v2])]
                 (recur (dec remaining)
                        s3
                        (conj result
                                 {:first-vector? (vector? first-arg)
                                  :result merged}))))))

(defn seeded-map-entry-elem
  [selector k v]
  (case selector
    0 nil
    1 {}
    2 {k v}
    3 [k v]
    4 (first {k v})
    5 [[k v] [:extra v]]
    6 (list k v)
    7 (list [k v])
    8 "kv"
    9 [k]
    [k v :extra]))

(emit-case :seeded-map-conj-corpus
           (loop [remaining 64
                  seed 230987
                  acc []]
             (if (zero? remaining)
               acc
               (let [s1 (next-merge-seed seed)
                     s2 (next-merge-seed s1)
                     s3 (next-merge-seed s2)
                     k1 (keyword (str "k" (mod s1 17)))
                     k2 (keyword (str "k" (mod s2 17)))
                     v1 (mod s2 101)
                     v2 (mod s3 101)
                     e1 (seeded-map-entry-elem (mod s1 11) k1 v1)
                     e2 (seeded-map-entry-elem (mod s2 11) k2 v2)]
                 (recur (dec remaining)
                        s3
                        (conj acc
                               {:conj-result (result #(conj {} e1 e2))
                                :merge-result (result #(merge {} e1 e2))
                                :transient-result (result #(transient-map-conj e1 e2))}))))))
