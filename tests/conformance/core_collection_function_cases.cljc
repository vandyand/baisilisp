;; Portable clojure.core collection, predicate, atom, and function-helper
;; semantics. Outputs are normalized to data values so host object identity and
;; map iteration order do not affect differential comparison.

#?(:clj (import '[java.io BufferedReader StringReader StringWriter])
   :lpy (import io))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn string-writer []
  #?(:clj (StringWriter.)
     :lpy (io/StringIO)))

(defn writer-value [writer]
  #?(:clj (str writer)
     :lpy (.getvalue writer)))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn sorted-entries [m]
  (vec (sort (seq m))))

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(defn seeded-vector [seed]
  (loop [remaining (+ 3 (mod seed 7))
         current seed
         result []]
    (if (zero? remaining)
      result
      (let [next (next-seed current)]
        (recur (dec remaining)
               next
               (conj result (- (mod next 9) 4)))))))

(defrecord CoreHelperRecord [a b])

(emit-case :predicates-and-small-constructors
           {:any [(any? nil)
                  (any? false)
                  (any? [])
                  (any? (fn [] nil))]
            :coll [(coll? [])
                   (coll? {})
                   (coll? #{})
                   (coll? nil)
                   (coll? "abc")]
            :associative [(associative? {})
                          (associative? [])
                          (associative? #{})
                          (associative? nil)]
            :bytes [(bytes? (byte-array [1 2 3]))
                    (bytes? [1 2 3])
                    (bytes? nil)]
            :fn [(fn? (fn [] nil))
                 (fn? +)
                 (fn? {})
                 (fn? nil)]
            :numeric [(float? 1.0)
                      (float? 1)
                      (int? 1)
                      (int? 1.0)
                      (int? true)
                      (nat-int? 0)
                      (nat-int? -1)
                      (nat-int? 1.0)
                      (neg-int? -1)
                      (neg-int? 0)]
            :inst [(inst? #inst "1970-01-01T00:00:00.000-00:00")
                   (inst? "1970-01-01")
                   (inst? nil)]
            :map-entry (let [entry (first {:a 1})]
                         [(map-entry? entry)
                          (map-entry? [:a 1])
                          (map-entry? nil)
                          (vec entry)])
            :array-map (vec (seq (array-map :a 1 :b 2 :c 3)))})

(emit-case :atom-transient-and-flush-helpers
           (let [a (atom 0)
                 cas [(compare-and-set! a 1 2)
                      @a
                      (compare-and-set! a 0 5)
                      @a]
                 t (-> (transient {:a 1})
                       (assoc! :b 2 :c 3))]
             (let [writer (string-writer)]
               (binding [*out* writer]
                 (print "before")
                 (flush)
                 (print "-after"))
               {:cas cas
                :assoc (sorted-entries (persistent! t))
                :flush (writer-value writer)})))

(emit-case :function-combinators-and-completing
           (let [not-even? (complement even?)
                 always (constantly :constant)
                 cmp (comparator >)
                 rf (completing conj #(conj % :done))]
             {:complement [(not-even? 1)
                           (not-even? 2)
                           ((complement =) 1 2)
                           ((complement =) 1 1)]
              :constantly [(always)
                           (always 1 2 3)]
              :comparator [(cmp 3 2)
                           (cmp 2 3)
                           (cmp 2 2)
                           (vec (sort cmp [1 4 2 3]))]
              :completing [(rf)
                           (rf [:x])
                           (rf [:x] :y)
                           (transduce (map inc) rf [] [1 2 3])]}))

(emit-case :lazy-sequence-helpers
           {:bounded-count [(bounded-count 3 (range))
                            (bounded-count 10 [1 2 3])
                            (bounded-count 0 [1 2 3])]
            :butlast [(vec (or (butlast [1 2 3]) []))
                      (vec (or (butlast [1]) []))
                      (vec (or (butlast nil) []))]
            :cycle [(vec (take 8 (cycle [:a :b :c])))
                    (seq (take 3 (cycle [])))]
            :dedupe [(vec (dedupe [1 1 2 2 2 3 1 1]))
                     (vec (sequence (dedupe) [1 1 2 2 1]))]
            :distinct? [(rejected? #(distinct?))
                        (distinct? 1)
                        (distinct? 1 2 3)
                        (distinct? 1 2 1)
                        (distinct? nil false nil)]
            :dorun (let [seen (atom [])]
                     [(dorun (map #(swap! seen conj %) [1 2 3]))
                      @seen])
            :drop-last [(vec (drop-last [1 2 3]))
                        (vec (drop-last 2 [1 2 3 4]))
                        (vec (drop-last 10 [1 2]))]
            :drop-while [(vec (drop-while neg? [-3 -2 0 1]))
                         (vec (sequence (drop-while #(< % 3)) [1 2 3 2 4]))]
            :filterv [(filterv odd? [1 2 3 4])
                      (filterv nil? [nil false nil true])]
            :flatten [(vec (flatten [1 [2 nil] '((3 4)) []]))
                      (vec (flatten nil))
                      (vec (flatten 42))]
            :frequencies [(sorted-entries (frequencies [:a :b :a :c :b :a]))
                          (sorted-entries (frequencies []))]
            :group-by [(sorted-entries (group-by count ["a" "bb" "" "c"]))
                       (sorted-entries
                        (group-by #(cond
                                     (neg? %) :neg
                                     (zero? %) :zero
                                     :else :pos)
                                  [-2 0 1 -3 2]))
                       (sorted-entries (group-by identity []))]
            :interpose [(vec (interpose :sep [:a :b :c]))
                        (vec (interpose :sep [:a]))
                        (vec (interpose :sep []))
                        (vec (sequence (interpose :sep) [:a :b :c]))]
            :interleave [(vec (interleave [:a :b :c] [1 2]))
                         (vec (interleave [:a :b] [1 2 3] [:x :y :z]))
                         (vec (interleave))
                         (vec (or (interleave nil [1 2]) []))
                         (vec (or (interleave [:a :b]) []))]
            :line-seq (vec (line-seq #?(:clj (BufferedReader.
                                              (StringReader. "alpha\r\nbeta\n"))
                                       :lpy (io/StringIO "alpha\r\nbeta\n"))))
            :iterator-seq (vec (iterator-seq #?(:clj (.iterator [1 2 3])
                                                :lpy (python/iter [1 2 3]))))})

(emit-case :function-helper-boundaries
           {:every-pred [(let [p (every-pred pos? odd?)]
                           [(p)
                            (p 1)
                            (p 1 3 5)
                            (p 1 2)
                            (p -1 3)])
                         (let [calls (atom 0)
                               p (every-pred (constantly false)
                                             (fn [_]
                                               (swap! calls inc)
                                               true))]
                           [(p :x) @calls])]
            :memoize (let [calls (atom 0)
                           f (memoize (fn [x]
                                        (swap! calls inc)
                                        (case x
                                          :nil nil
                                          :false false
                                          (* x x))))]
                       [(f :nil)
                        (f :nil)
                        (f :false)
                        (f :false)
                        (f 3)
                        (f 3)
                        @calls])
            :min-key [(min-key count "bbb")
                      (min-key count "bbb" "a" "cc")
                      (min-key count "aa" "bb" "c")
                      (min-key count "aa" "bb")
                      (rejected? #(min-key count))]
            :max-key [(max-key count "a")
                      (max-key count "a" "bbb" "cc")
                      (max-key count "a" "bb" "cc")
                      (max-key count "aa" "bb")
                      (rejected? #(max-key count))]
            :merge-with [(sorted-entries
                          (merge-with + {:a 1 :b 2} {:a 3 :c 4} nil {:b 5}))
                         (sorted-entries (merge-with conj {:a [1]} {:a 2 :b 3}))
                         (merge-with +)
                         (sorted-entries (merge-with + nil {:a 1}))]
            :iteration [(vec (iteration (fn [k]
                                          (when (< k 4)
                                            {:value (* k k)
                                             :next (inc k)}))
                                        :initk 0
                                        :vf :value
                                        :kf :next))
                        (vec (iteration (fn [k]
                                          (when (< k 5)
                                            k))
                                        :initk 1
                                        :somef #(and (some? %) (odd? %))
                                        :vf inc
                                        :kf #(+ % 2)))]})

(emit-case :sequence-segmentation-and-reduction-helpers
           {:predicate-combinators
            {:identity [(identity nil)
                        (identity false)
                        (identity :value)]
             :partial [((partial vector :a) :b :c)
                       ((partial + 1 2) 3 4)
                       ((partial str "pre-") "post")]
             :some-fn [(let [p (some-fn nil? keyword?)]
                         [(p nil)
                          (p :x)
                          (p "x")
                          (p "x" :y)])
                       (let [calls (atom 0)
                             p (some-fn (constantly nil)
                                        (fn [_]
                                          (swap! calls inc)
                                          false))]
                         [(p :x) @calls])]
             :not-preds [(not-any? neg? [0 1 2])
                         (not-any? neg? [0 -1 2])
                         (not-every? pos? [1 2 3])
                         (not-every? pos? [1 0 3])]}
            :split-and-take
            {:take-while [(vec (take-while neg? [-3 -1 0 -2]))
                          (vec (sequence (take-while #(< % 4)) [1 2 4 3]))]
             :take-nth [(vec (take 6 (take-nth 2 (range))))
                        (vec (take 5 (take-nth 0 [:a :b :c])))
                        (vec (sequence (take-nth 3) (range 10)))]
             :take-last [(vec (or (take-last 2 [:a :b :c :d]) []))
                         (vec (or (take-last 10 [:a]) []))
                         (vec (or (take-last 0 [:a]) []))]
             :split-at [(mapv vec (split-at 2 [:a :b :c :d]))
                        (mapv vec (split-at -1 [:a :b]))]
             :splitv-at [(let [[prefix suffix] (splitv-at 2 [:a :b :c])]
                           [(vector? prefix) prefix (vec suffix)])
                         (let [[prefix suffix] (splitv-at -1 [:a :b])]
                           [(vector? prefix) prefix (vec suffix)])]
             :split-with [(mapv vec (split-with neg? [-2 -1 0 -3]))
                          (mapv vec (split-with keyword? [:a :b "c" :d]))]}
            :partition-and-reductions
            {:partitionv [(partitionv 2 [1 2 3 4 5])
                          (partitionv 3 2 [1 2 3 4 5])
                          (partitionv 3 2 [:pad] [1 2 3 4 5])]
             :partitionv-all [(partitionv-all 2 [1 2 3 4 5])
                              (partitionv-all 3 2 [1 2 3 4 5])]
             :partition-by [(mapv vec (partition-by odd? [1 3 2 4 5 7 8]))
                            (vec (sequence (partition-by count)
                                           ["a" "b" "cc" "" "d"]))]
             :reductions [(vec (reductions + [1 2 3 4]))
                          (vec (reductions + []))
                          (vec (reductions conj [] [:a :b :c]))
                          (vec (reductions + 10 [1 2 3]))]}
            :repeat-replace-run
            {:repeat [(vec (take 4 (repeat :x)))
                      (vec (repeat 3 :x))
                      (vec (repeat -1 :x))]
             :replicate [(vec (replicate 3 :x))
                         (vec (replicate 0 :x))
                         (vec (replicate -1 :x))]
             :repeatedly (let [counter (atom 0)]
                           [(vec (repeatedly 4 #(swap! counter inc)))
                            @counter])
             :replace [(replace {:a nil :b false :c 3} [:a :b :c :d])
                       (vec (replace {:a nil :b false :c 3} '(:a :b :c :d)))
                       (vec (sequence (replace {:a nil :b false :c 3})
                                      [:a :b :c :d]))]
             :run! (let [seen (atom [])]
                     [(run! #(swap! seen conj %) [:a :b :c])
                      @seen])}})

(emit-case :collection-reference-navigation-and-binding-helpers
           {:navigation
            {:nested [(ffirst [[1 2] [3 4]])
                      (nfirst [[1 2] [3 4]])
                      (nnext [1 2 3])
                      (nnext [1])
                      (nthrest [:a :b :c :d] 2)
                      (nthrest [:a :b] 10)
                      (nthrest nil 3)
                      (rejected? #(nthrest nil nil))
                      (nthnext [:a :b :c :d] 2)
                      (nthnext [:a :b] 10)
                      (nthnext nil 3)]
             :list-star [(vec (list* [1 2]))
                         (vec (list* :a [:b :c]))
                         (vec (list* :a :b [:c :d]))
                         (list? (list* :a [:b]))
                         (list? [])
                         (list? '())]}
            :capability-predicates
            {:counted [(counted? [])
                       (counted? {})
                       (counted? '(:a :b))
                       (counted? (range))
                       (counted? nil)]
             :indexed [(indexed? [])
                       (indexed? '(:a :b))
                       (indexed? {})
                       (indexed? nil)]
             :reversible [(reversible? [])
                          (reversible? (sorted-map :b 2 :a 1))
                          (reversible? '(:a :b))
                          (reversible? nil)]
             :sequential [(sequential? [])
                          (sequential? '(:a :b))
                          (sequential? {})
                          (sequential? nil)]}
            :identifier-and-scalar-predicates
            {:ident [(ident? :a)
                     (ident? 'a)
                     (ident? "a")]
             :qualified [(qualified-ident? :a/b)
                         (qualified-ident? 'a/b)
                         (qualified-ident? :a)
                         (qualified-keyword? :a/b)
                         (qualified-keyword? 'a/b)
                         (qualified-symbol? 'a/b)
                         (qualified-symbol? :a/b)]
             :simple [(simple-ident? :a)
                      (simple-ident? 'a)
                      (simple-ident? :a/b)
                      (simple-keyword? :a)
                      (simple-keyword? :a/b)
                      (simple-symbol? 'a)
                      (simple-symbol? 'a/b)]
             :special [(special-symbol? 'if)
                       (special-symbol? 'let)
                       (special-symbol? 'not-a-special)]
             :numeric [(pos-int? 1)
                       (pos-int? 0)
                       (pos-int? -1)
                       (pos-int? 1.0)
                       (rational? 1)
                       (rational? 1/2)
                       (rational? 1.5)
                       (rational? true)]}
            :reduce-kv-and-map-updates
            {:map-reduce (sorted-entries
                          (reduce-kv (fn [acc k v]
                                       (assoc acc v k))
                                     {}
                                     {:a 1 :b 2 :c 3}))
             :vector-reduce (reduce-kv (fn [acc k v]
                                         (conj acc [k v]))
                                       []
                                       [:a :b :c])
             :record-reduce (sorted-entries
                             (reduce-kv (fn [acc k v]
                                          (assoc acc k v))
                                        {}
                                        (->CoreHelperRecord 1 2)))
             :early-reduced (reduce-kv (fn [acc k v]
                                         (if (= k :b)
                                           (reduced [:stopped acc])
                                           (conj acc [k v])))
                                       []
                                       (array-map :a 1 :b 2 :c 3))
             :update-keys (let [m (with-meta {:a 1 :b 2} {:source :fixture})]
                            [(sorted-entries (update-keys m name))
                             (meta (update-keys m name))])
             :update-vals (let [m (with-meta {:a "x" :b "yy"} {:source :fixture})]
                            [(sorted-entries (update-vals m count))
                             (meta (update-vals m count))])}
            :metadata-and-reference-values
            {:vary-meta [(meta (vary-meta (with-meta [1 2] {:a 1})
                                          assoc
                                          :b 2))
                         (meta (vary-meta (with-meta [1 2] {:a 1})
                                          dissoc
                                          :a))
                         (meta (vary-meta (with-meta [1 2] {:a 1})
                                          (constantly nil)))]
             :volatile (let [v (volatile! :a)]
                         [(volatile? v)
                          (volatile? (atom :a))
                          @v
                          (vreset! v :b)
                          @v
                          (vswap! v name)
                          @v])
             :atom-values (let [a (atom 1)]
                            [(reset-vals! a 2)
                             @a
                             (swap-vals! a + 3)
                             @a])
             :validator (let [a (atom 0)]
                          [(nil? (get-validator a))
                           (set-validator! a int?)
                           (boolean (get-validator a))
                           (rejected? #(reset! a :bad))
                           @a])
             :watch-removal (let [seen (atom [])
                                  a (atom 0)]
                              (add-watch a :capture
                                         (fn [_ _ old new]
                                           (swap! seen conj [old new])))
                              (reset! a 1)
                              (remove-watch a :capture)
                              (reset! a 2)
                              @seen)}
            :binding-macros
            {:if-let [(if-let [x 1] x :else)
                      (if-let [x false] x :else)]
             :if-some [(if-some [x false] x :else)
                       (if-some [x nil] x :else)]
             :when-let [(when-let [x :value] x)
                        (when-let [x false] x)]
             :when-some [(when-some [x false] x)
                         (when-some [x nil] x)]
             :when-first [(when-first [x [false :tail]] [:ran x])
                          (when-first [x [nil :tail]] [:ran x])
                          (when-first [x []] [:ran x])]}})

(emit-case :threading-macro-helpers
           {:as-> (as-> 5 v
                    (+ v 2)
                    [v (* v 3)]
                    (conj v :done))
            :cond->> (cond->> [1 2 3]
                       true (map inc)
                       false (filter even?)
                       true (take 2)
                       true vec)})

(emit-case :seeded-collection-fuzz
           (mapv (fn [seed]
                   (let [values (seeded-vector seed)]
                     {:input values
                      :bounded (bounded-count 4 values)
                      :dedupe (vec (dedupe values))
                      :drop-last (vec (drop-last (mod seed 4) values))
                      :drop-while (vec (drop-while neg? values))
                      :filterv (filterv pos? values)
                      :frequencies (sorted-entries (frequencies values))
                      :group-by (sorted-entries
                                 (group-by #(if (neg? %) :neg :non-neg) values))
                      :interleave (vec (interleave values (reverse values)))
                      :interpose (vec (interpose :sep values))
                      :partition-by (mapv vec (partition-by neg? values))
                      :partitionv-all (partitionv-all 3 2 values)
                      :reductions (vec (reductions + values))
                      :replace (replace {0 nil -1 false 1 :one} values)
                      :navigation [(vec (nthrest values (mod seed 6)))
                                   (vec (or (nthnext values (mod seed 6)) []))
                                   (ffirst [(take 2 values)])
                                   (vec (list* :seed values))]
                      :reduce-kv (reduce-kv (fn [acc k v]
                                              (assoc acc k v))
                                            {}
                                            values)
                      :update-vals (sorted-entries
                                    (update-vals {:sum (reduce + 0 values)
                                                  :count (count values)}
                                                 inc))
                      :split-at (mapv vec (split-at (mod seed 5) values))
                      :take-nth (vec (take-nth (inc (mod seed 3)) values))
                      :merge-with (sorted-entries
                                   (merge-with + {:sum (reduce + 0 values)}
                                               {:sum (count values)
                                                :seed seed}))
                      :min-key (apply min-key abs values)
                      :max-key (apply max-key abs values)
                      :distinct? (apply distinct? values)}))
                 (take 32 (iterate next-seed 610839776))))
