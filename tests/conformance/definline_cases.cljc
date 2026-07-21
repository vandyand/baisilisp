;; Portable definline cases. The harness evaluates this exact source in Clojure
;; and Basilisp and compares only deterministic EDN values.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(def returned
  (definline plus-one "increment a number" {:custom :metadata}
    [x]
    `(+ 1 ~x)))

(emit-case :definition
           [(identical? returned #'plus-one)
            (plus-one 41)
            ^:no-inline (plus-one 41)
            (boolean (:inline (meta #'plus-one)))
            (:doc (meta #'plus-one))
            (:custom (meta #'plus-one))])

(definline expand-twice [x] `(+ ~x ~x))

(let [inline-calls (atom 0)]
  (emit-case :side-effects
             [(expand-twice (swap! inline-calls inc))
              @inline-calls]))
