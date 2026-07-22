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
