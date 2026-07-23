;; Portable clojure.walk/basilisp.walk conformance cases. These focus on
;; observable data, metadata, sorted collection preservation, traversal order,
;; and generated nested data rather than host class names.

(require '[clojure.walk :as walk])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn generated-form [depth seed]
  (if (zero? depth)
    (case (mod seed 6)
      0 :leaf
      1 (str "k" seed)
      2 seed
      3 nil
      4 (symbol (str "sym" seed))
      true)
    (case (mod (+ depth seed) 5)
      0 [(generated-form (dec depth) (+ seed 1))
         (generated-form (dec depth) (+ seed 2))]
      1 (list (generated-form (dec depth) (+ seed 1))
              (generated-form (dec depth) (+ seed 2)))
      2 {(str "k" seed) (generated-form (dec depth) (+ seed 1))
         (keyword (str "kw" seed)) (generated-form (dec depth) (+ seed 2))}
      3 #{(generated-form (dec depth) (+ seed 1))
          (generated-form (dec depth) (+ seed 2))}
      (sorted-map (keyword (str "a" seed)) (generated-form (dec depth) (+ seed 1))
                  (keyword (str "b" seed)) (generated-form (dec depth) (+ seed 2))))))

(defn count-nodes [form]
  (let [counter (atom 0)]
    (walk/postwalk (fn [x] (swap! counter inc) x) form)
    @counter))

(defn replace-leaves [form]
  (walk/postwalk-replace {nil :nil
                          true :true
                          :leaf :replaced-leaf}
                         form))

(def required-publics
  ["keywordize-keys"
   "macroexpand-all"
   "postwalk"
   "postwalk-demo"
   "postwalk-replace"
   "prewalk"
   "prewalk-demo"
   "prewalk-replace"
   "stringify-keys"
   "walk"])

(defmacro fixture-leaf [x]
  `[:leaf ~x])

(defmacro fixture-wrapper [a b]
  `(fixture-leaf [~a ~b]))

(emit-case :public-surface
           (let [publics (set (map name (keys (ns-publics #?(:clj 'clojure.walk
                                                             :lpy 'basilisp.walk)))))]
             {:required-present (mapv #(contains? publics %) required-publics)}))

(emit-case :basic-replacement-and-key-transforms
           {:postwalk-replace (walk/postwalk-replace {:a 1 :b 2 nil :nil}
                                                     [:a {:b nil} [:c :a]])
            :prewalk-replace (walk/prewalk-replace {:a 1 [:a] :vector}
                                                   [:a [:a] {:x [:a]}])
            :keywordize (walk/keywordize-keys {"a" 1
                                               :b {"c" 3}
                                               "nested" [{"d" 4}]})
            :stringify (walk/stringify-keys {:a 1
                                             "b" {:c 3}
                                             :nested [{:d 4}]})})

(emit-case :metadata-and-sorted-preservation
           (let [sorted-map-result (walk/postwalk identity
                                                  (with-meta (sorted-map :b 2 :a 1)
                                                    {:m :map}))
                 sorted-set-result (walk/postwalk identity
                                                  (with-meta (sorted-set 3 1 2)
                                                    {:m :set}))
                 vector-result (walk/postwalk identity
                                             (with-meta [:a {:b 2}]
                                               {:m :vector}))
                 list-result (walk/postwalk identity
                                           (with-meta '(:a {:b 2})
                                             {:m :list}))]
             {:sorted-map? (sorted? sorted-map-result)
              :sorted-map-keys (mapv key sorted-map-result)
              :sorted-map-meta (meta sorted-map-result)
              :sorted-set? (sorted? sorted-set-result)
              :sorted-set-seq (vec sorted-set-result)
              :sorted-set-meta (meta sorted-set-result)
              :vector-meta (meta vector-result)
              :list-meta (meta list-result)}))

(emit-case :walk-order-and-macroexpand
           (let [pre-order (atom [])
                 post-order (atom [])
                 form '(fixture-wrapper 10 4)
                 prewalk-result (walk/prewalk (fn [x] (swap! pre-order conj x) x)
                                              [:a [:b :c]])
                 postwalk-result (walk/postwalk (fn [x] (swap! post-order conj x) x)
                                                [:a [:b :c]])]
             {:prewalk prewalk-result
              :pre-order @pre-order
              :postwalk postwalk-result
              :post-order @post-order
              :macroexpand-all (walk/macroexpand-all form)}))

(emit-case :generated-corpus
           (mapv (fn [seed]
                   (let [form (generated-form 4 seed)
                         keywordized (walk/keywordize-keys form)
                         stringified (walk/stringify-keys keywordized)]
                     {:seed seed
                      :nodes (count-nodes form)
                      :replace (replace-leaves form)
                      :roundtrip-nodes (count-nodes stringified)
                      :postwalk-identity (= form (walk/postwalk identity form))
                      :prewalk-identity (= form (walk/prewalk identity form))}))
                 (range 48)))
