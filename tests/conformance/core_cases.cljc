;; Portable collection, sequence, metadata, and hierarchy cases. The
;; differential harness evaluates this exact source in Clojure and Basilisp.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(let [value (-> {:account {:positions [1 2]}}
                (assoc-in [:account :cash] 10)
                (update-in [:account :positions] conj 3))]
  (emit-case :nested-associative
             {:value value
              :selected (select-keys (:account value) [:cash :positions])
              :missing (get-in value [:account :missing] :absent)}))

(emit-case :lazy-sequences
           {:mapped (into [] (map #(* % %) (range 5)))
            :partitioned (into [] (partition 2 (range 5)))
            :distinct (into [] (distinct [1 2 1 3 2]))})

(emit-case :transducers
           {:into (into [] (comp (map inc) (filter even?)) (range 6))
            :early-reduce
            (reduce (fn [result value]
                      (if (= value 3)
                        (reduced result)
                        (conj result value)))
                    []
                    (range 6))})

(let [value (with-meta [1 2] {:source :conformance})]
  (emit-case :metadata {:value value :metadata (meta value)}))

(let [h (derive (make-hierarchy) :conformance/child :conformance/parent)]
  (emit-case :hierarchy
             {:direct (isa? h :conformance/child :conformance/parent)
              :parents (parents h :conformance/child)
              :ancestors (ancestors h :conformance/child)}))

(let [exception (ex-info "conformance exception" {:kind :portable})]
  (emit-case :exception-data
             {:message (ex-message exception)
              :data (ex-data exception)
              :cause (ex-cause exception)}))

(let [value {:alpha [1 nil] :beta #{:x :y}}]
  (emit-case :reader-printer {:read-back (read-string (pr-str value))
                               :printed? (string? (pr-str value))}))
