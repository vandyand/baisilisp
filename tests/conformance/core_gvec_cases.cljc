;; Public clojure.gvec behavior hardening. The bundled clojure.gvec source is
;; not requireable directly, so these cases verify the observable typed-vector
;; contract through clojure.core/vector-of.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(emit-case :vector-of-persistent-update-contracts
           (let [base (vector-of :int 1.9)
                 with-meta-value (with-meta (vector-of :int 1) {:kind :typed})]
             {:initial [(vector? base)
                        (= [1] base)
                        (= base [1])
                        (= (hash base) (hash [1]))]
              :conj (conj base 2.9 -3.9)
              :assoc (assoc base 0 9.9 1 8.1)
              :pop (pop (conj base 2.9))
              :subvec (subvec (conj base 2.9 3.9 4.9) 1 3)
              :boolean [(vector-of :boolean true false 1 nil)
                        (conj (vector-of :boolean false) 1 nil)
                        (assoc (vector-of :boolean true) 0 nil 1 1)]
              :meta [(meta with-meta-value)
                     (meta (conj with-meta-value 2.9))
                     (meta (assoc with-meta-value 0 3.9))
                     (meta (pop (conj with-meta-value 2.9)))
                     (meta (empty with-meta-value))]
              :empty [(empty? (empty with-meta-value))
                      (conj (empty with-meta-value) 7.9)]}))

(emit-case :vector-of-update-rejection-boundaries
           {:construction [(rejected? #(vector-of :byte 128))
                           (rejected? #(vector-of :char "a"))
                           (rejected? #(vector-of :int 2147483648))]
            :persistent [(rejected? #(conj (vector-of :byte 1) 128))
                         (rejected? #(assoc (vector-of :char \a) 0 "a"))
                         (rejected? #(conj (vector-of :int 1) 2147483648))]
            :transient [(rejected? #(transient (vector-of :int 1)))
                        (rejected? #(transient (with-meta (vector-of :int 1)
                                                {:kind :typed})))]})

(emit-case :vector-of-seeded-update-fuzz
           (mapv (fn [n]
                   (let [base (apply vector-of
                                     (cons :int
                                           (map #(+ (* n 10) % 0.9)
                                                (range (inc (mod n 7))))))
                         c1 (conj base (+ 100 n 0.9))
                         a1 (assoc c1 0 (- (+ n 0.9)))
                         p1 (pop a1)]
                     {:n n
                      :base base
                      :conj c1
                      :assoc a1
                      :pop p1
                      :sum (reduce + 0 a1)}))
                 (range 24)))
