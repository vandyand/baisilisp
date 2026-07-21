;; Clojure's #= reader macro is controlled by the dynamic *read-eval* Var.
;; Keep the exercised forms portable and render only ordinary EDN values.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch Exception _ true)))

(emit-case :reader-eval
           [(read-string "#=(+ 20 22)")
            (read-string "[#=(+ 1 2) #=(+ 3 4)]")
            (binding [*read-eval* false]
              (rejected? #(read-string "#=(+ 20 22)")))
            (binding [*read-eval* :unknown]
              (rejected? #(read-string "1")))])
