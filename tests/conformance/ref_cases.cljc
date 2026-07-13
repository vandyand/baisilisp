;; Portable Ref cases. The differential harness evaluates this exact source in
;; Clojure and Basilisp and compares the EDN lines it emits.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(let [first  (ref 1)
      second (ref 2)
      result (dosync (alter first + 2) (ref-set second 6) :committed)]
  (emit-case :multi-ref
             {:result result
              :values [@first @second]}))

(let [value (ref 1)]
  (dosync
   (alter value inc)
   (dosync (alter value inc)))
  (emit-case :nested-dosync @value))

(let [value  (ref 0)
      events (atom [])]
  (add-watch value :record (fn [_ _ old new] (swap! events conj [old new])))
  (dosync (alter value inc) (alter value + 2))
  (emit-case :watch-after-commit {:value @value :events @events}))

(let [value (ref 2 :validator even?)]
  (emit-case :validator (dosync (alter value + 2))))

(let [value  (ref 1)
      result (dosync (commute value + 2))
      final  @value]
  (emit-case :commute {:result result :value final}))

(let [value (ref 5)]
  (emit-case :ensure (dosync (ensure value))))

(let [value (ref 1 :meta {:conformance :ref})]
  (emit-case :metadata (meta value)))
