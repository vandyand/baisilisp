;; Portable clojure.core.rrb-vector/basilisp.core.rrb-vector behavior.

(require '[clojure.core.rrb-vector :as rrb])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn summary [value]
  {:value value
   :vector (vector? value)
   :count (count value)
   :meta (meta value)})

(defn generated-vector [seed size]
  (vec
   (map (fn [idx]
          (- (mod (+ (* seed 37) (* idx 17) (* idx idx)) 101) 50))
        (range size))))

(defn slice-summary [v start end]
  {:start start
   :end end
   :result (rrb/subvec v start end)
   :expected (vec (take (- end start) (drop start v)))
   :meta (meta (rrb/subvec v start end))})

(emit-case :public-surface
           (sort (map name (keys (ns-publics #?(:clj 'clojure.core.rrb-vector
                                                :lpy 'basilisp.core.rrb-vector))))))

(emit-case :constructors
           {:empty (summary (rrb/vector))
            :values (summary (rrb/vector 1 2 3))
            :vec-list (summary (rrb/vec '(1 2 3)))
            :vec-nil (summary (rrb/vec nil))
            :vector-of (summary (rrb/vector-of :int 1 2 3))})

(emit-case :catvec-behavior
           {:zero (summary (rrb/catvec))
            :one (summary (rrb/catvec (with-meta [1 2] {:source :left})))
            :two (summary (rrb/catvec (with-meta [1] {:source :left})
                                      (with-meta [2] {:source :right})))
            :empty-left-plain-right (summary (rrb/catvec (with-meta [] {:source :left})
                                                         [1]))
            :empty-left-meta-right (summary (rrb/catvec (with-meta [] {:source :left})
                                                        (with-meta [1] {:source :right})))
            :both-empty (summary (rrb/catvec (with-meta [] {:source :left})
                                             (with-meta [] {:source :right})))
            :many (summary (rrb/catvec [1] [2 3] [] [4]))
            :reject-left-list (rejected? #(rrb/catvec '(1) [2]))
            :reject-right-list (rejected? #(rrb/catvec [1] '(2)))})

(emit-case :subvec-behavior
           {:two-arity (summary (rrb/subvec (with-meta [1 2 3 4] {:source :slice}) 2))
            :three-arity (summary (rrb/subvec (with-meta [1 2 3 4] {:source :slice}) 1 3))
            :empty (summary (rrb/subvec [1 2] 1 1))
            :reject-non-vector (rejected? #(rrb/subvec '(1 2) 0 1))
            :reject-out-of-bounds (rejected? #(rrb/subvec [1] 2))})

(emit-case :generated-catvec-corpus
           (mapv (fn [seed]
                   (let [left (with-meta (generated-vector seed (mod seed 9))
                                {:seed seed})
                         right (generated-vector (+ seed 3) (mod (+ seed 4) 9))
                         joined (rrb/catvec left right)]
                     {:seed seed
                      :left-count (count left)
                      :right-count (count right)
                      :result joined
                      :expected (vec (concat left right))
                      :meta (meta joined)}))
                 (range 24)))

(emit-case :generated-subvec-corpus
           (mapv (fn [seed]
                   (let [size (+ 1 (mod (+ seed 5) 16))
                         v (with-meta (generated-vector seed size) {:seed seed})
                         start (mod (* seed 3) (inc size))
                         width (mod (+ seed 2) (inc (- size start)))
                         end (+ start width)]
                     (slice-summary v start end)))
                 (range 32)))
