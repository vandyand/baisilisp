;; Broad shared-core semantic probes. These cases deliberately avoid host class
;; names and exception text so the differential runner can compare values only.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn errors? [f]
  (try
    (f)
    false
    (catch Exception _ true)))

(emit-case :seq-boundaries
           {:empty-seqs [(seq nil)
                         (seq [])
                         (seq '())
                         (seq {})
                         (seq #{})
                         (seq "")]
            :non-empty [(vec (seq [1 2]))
                        (vec (seq '(1 2)))
                        (vec (seq "ab"))
                        (into #{} (map vec) (seq {:a 1 :b 2}))]
            :next-rest [(next [1])
                        (vec (rest [1]))
                        (vec (next [1 2]))
                        (vec (rest [1 2]))]})

(emit-case :collection-edge-core
           {:empties [(empty? nil)
                      (empty? [])
                      (empty? '())
                      (empty? {})
                      (empty? #{})
                      (empty? "")
                      (empty? [nil])]
            :not-empty [(not-empty nil)
                        (not-empty [])
                        (not-empty "")
                        (not-empty [nil])
                        (not-empty {:a nil})]
            :fnext-last [(fnext nil)
                         (fnext [])
                         (fnext [1])
                         (fnext [1 nil])
                         (fnext [1 2])
                         (last nil)
                         (last [])
                         (last [nil])
                         (last [1 2 nil])]
            :reverse [(vec (reverse nil))
                      (vec (reverse []))
                      (vec (reverse [1 2 3]))
                      (vec (reverse "ba"))]
            :set [(set nil)
                  (set [])
                  (set "aba")
                  (set {:a 1 :b 2})]
            :merge [(merge)
                    (merge nil)
                    (merge nil {:a 1})
                    (merge {:a 1} nil {:a 2 :b nil})]})

(emit-case :sort-and-sort-by-boundaries
           {:numbers [(vec (sort [3 1 2]))
                      (vec (sort > [3 1 2]))
                      (vec (sort-by :rank [{:id :b :rank 2}
                                           {:id :a :rank 1}
                                           {:id :c :rank 1}]))
                      (vec (sort-by count ["bbb" "" "cc" "a"]))]
            :maps [(vec (sort {:b 2 :a 1}))
                   (vec (sort-by val {:b 2 :a 1 :c 3}))]
            :strings [(vec (sort "cba"))
                      (vec (sort-by int "bca"))
                      (mapv str (sort "cba"))
                      (mapv int (sort "cba"))]})

(defn next-core-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(emit-case :seeded-collection-edge-corpus
           (loop [remaining 48
                  seed 424242
                  result []]
             (if (zero? remaining)
               result
               (let [s1 (next-core-seed seed)
                     s2 (next-core-seed s1)
                     s3 (next-core-seed s2)
                     values [(mod s1 11) (- (mod s2 11) 5) (mod s3 7)]
                     coll (case (mod s1 5)
                            0 values
                            1 (apply list values)
                            2 (apply hash-set values)
                            3 (zipmap [:a :b :c] values)
                            "caba")
                     ordered (if (or (map? coll) (set? coll))
                               (sort coll)
                               coll)]
                 (recur (dec remaining)
                        s3
                        (conj result
                              {:empty? (empty? coll)
                               :seqable? (seqable? coll)
                               :not-empty? (boolean (not-empty coll))
                               :last (last ordered)
                               :sorted (vec (sort coll))}))))))

(emit-case :indexed-boundaries
           {:nth [(nth [10 20] 0)
                  (nth [10 20] 1)
                  (nth [10 20] 9 :missing)
                  (nth nil 0 :missing)]
            :get [(get [10 20] 0)
                  (get [10 20] 2 :missing)
                  (get {:a nil} :a :missing)
                  (get {:a nil} :b :missing)]
            :contains [(contains? [10 20] 0)
                       (contains? [10 20] 2)
                       (contains? {:a nil} :a)
                       (contains? {:a nil} :b)]})

(emit-case :range-semantics
           {:finite (vec (range 1 6))
            :negative (vec (range 10 0 -3))
            :zero-step (vec (take 5 (range 1 10 0)))
            :empty [(vec (range 3 3))
                    (vec (range 0 -1))]
            :chunked [(chunked-seq? (seq (range 40)))
                      (chunked-seq? (seq (range 40 0 -1)))
                      (chunked-seq? (seq (range 1 10 0)))
                      (chunked-seq? (seq (range 0)))]})

(let [base (with-meta [1 2 3] {:tag :base})
      assoced (assoc base 1 :two)
      conjoined (conj base 4)
      popped (pop base)
      subvector (subvec base 1 3)]
  (emit-case :vector-metadata-and-shape
             {:values [assoced conjoined popped subvector]
              :metas [(meta assoced)
                      (meta conjoined)
                      (meta popped)
                      (meta subvector)]
              :peek-pop [(peek base) (pop [1]) (errors? #(pop []))]
              :assoc-extension [(assoc [1 2] 2 3)
                                (errors? #(assoc [1 2] 4 5))]}))

(let [base (with-meta {:a 1 :b nil} {:tag :map})
      assoced (assoc base :c 3)
      dissoced (dissoc base :a :missing)
      updated (update base :a inc)
      updated-missing (update base :missing (fnil inc 0))]
  (emit-case :map-update-semantics
             {:values [assoced dissoced updated updated-missing]
              :metas [(meta assoced)
                      (meta dissoced)
                      (meta updated)
                      (meta updated-missing)]
              :find [(vec (find base :a))
                     (find base :missing)]
              :select (select-keys base [:a :missing :b])}))

(let [[a b & more :as all] [1 2 3 4]
      {:keys [x y]
       :or {y :default}
       :as m} {:x 1}
      {plain :plain
       qualified :sample/key
       :keys [local]
       :sample/keys [key]} {:plain 0
                            :sample/key 1
                            :local 2}
      [nested-a {:keys [nested-b]}] [10 {:nested-b 20}]]
  (emit-case :destructuring
             {:sequential {:a a :b b :more more :all all}
              :map-defaults {:x x :y y :m m}
              :namespaced {:plain plain
                           :qualified qualified
                           :local local
                           :key key}
              :nested [nested-a nested-b]}))

(emit-case :set-and-map-as-functions
           {:set [(#{:a :b} :a)
                  (#{:a :b} :z)
                  (#{:a nil} nil)
                  (contains? #{nil} nil)]
            :map [({:a 1 :b nil} :a)
                  ({:a 1 :b nil} :b)
                  ({:a 1 :b nil} :z :missing)]})

(let [xf (comp (map inc) (filter even?) (take 3))
      completion (transduce xf conj [] (range 20))
      reduced-value (reduced {:done true})
      ensure-same (ensure-reduced reduced-value)
      ensure-new (ensure-reduced :value)]
  (emit-case :reduced-and-transducer-semantics
             {:completion completion
              :reduced? [(reduced? reduced-value)
                         (reduced? :value)
                         (identical? reduced-value ensure-same)
                         (reduced? ensure-new)]
              :values [@reduced-value
                       (unreduced reduced-value)
                       (unreduced :value)
                       @ensure-new]}))

(let [realizations (atom [])
      source (map (fn [x]
                    (swap! realizations conj x)
                    x)
                  (range 40))
      first-three (doall (take 3 source))
      after-take @realizations
      next-two (doall (take 2 (drop 3 source)))]
  (emit-case :lazy-realization-boundary
             {:first-three (vec first-three)
              :next-two (vec next-two)
              :realized-after-take after-take
              :realized-count-after-drop (count @realizations)}))

(emit-case :threading-and-conditionals
           {:some-> [(some-> {:a {:b 1}} :a :b inc)
                     (some-> {:a nil} :a :b inc)]
            :cond-> (cond-> {:a 1}
                      true (assoc :b 2)
                      false (assoc :c 3)
                      (= 1 1) (update :a inc))
            :case [(case :b
                     :a 1
                     :b 2
                     :fallback)
                   (case :z
                     :a 1
                     :b 2
                     :fallback)]})

(defmacro wrap-twice [form]
  `(let [value# ~form]
     [value# value#]))

(let [expanded (macroexpand '(wrap-twice (+ 1 2)))]
  (emit-case :reader-and-macro-semantics
             {:syntax-quote {:let-form? (= 'let* (first expanded))
                             :binding-count (count (second expanded))
                             :body-count (count (rest (rest expanded)))
                             :result (wrap-twice (+ 1 2))}
              :metadata [(select-keys (meta (read-string "^:private [1]"))
                                      [:private])
                         (:tag (meta (read-string "^{:tag :x} []")))]
              :discard (read-string "[1 #_ignored 2]")}))
