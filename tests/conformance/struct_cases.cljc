;; ``create-struct`` creates a fixed-key basis. Struct maps remain maps while
;; accessors reject both ordinary maps and values from a different basis.

(ns conformance.struct-cases)

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn errors? [f]
  (try
    (f)
    false
    (catch Exception _ true)))

(let [basis       (create-struct :a :b)
      other-basis (create-struct :a :b)
      value       (struct-map basis :a 1 :b 2 :extra 3)
      get-a       (accessor basis :a)]
  (emit-case :fixed-struct-map
             {:map-equality? (= value {:a 1 :b 2 :extra 3})
              :hash-equality? (= (hash value) (hash {:a 1 :b 2 :extra 3}))
              :field-order? (= [[:a 1] [:b 2] [:extra 3]] (vec value))
              :accessor-value (= 1 (get-a value))
              :into-preserves-basis? (= 1 (get-a (into value {:more 4})))
              :extension-removable? (= (struct basis 1 2)
                                       (dissoc value :extra))
              :fixed-key-protected? (errors? #(dissoc value :a))
              :transient-rejected? (errors? #(transient value))
              :plain-map-rejected? (errors? #(get-a {:a 1 :b 2}))
              :other-basis-rejected? (errors? #(get-a (struct other-basis 1 2)))
              :empty-preserves-keys? (= {:a nil :b nil} (empty value))
              :empty-clears-meta? (nil? (meta (empty (with-meta value {:m true}))))}))
