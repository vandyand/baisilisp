(ns conformance.unresolved-vars-cases)

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(emit-case :unresolved-vars
           {:default-false? (false? *allow-unresolved-vars*)
            :eval-fails? (binding [*allow-unresolved-vars* true]
                           (try
                             (eval 'unresolved-symbol)
                             false
                             (catch #?(:clj IllegalArgumentException
                                       :lpy python/Exception) _
                               true)))
            :macroexpand-preserved?
            (= '(unresolved-macro 1)
               (binding [*allow-unresolved-vars* true]
                 (macroexpand '(unresolved-macro 1))))
            :restored? (false? *allow-unresolved-vars*)})
