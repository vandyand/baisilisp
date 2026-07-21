;; Dynamic *repl* Var surface shared by Clojure and Basilisp.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(emit-case :repl-binding
           [*repl*
            (binding [*repl* true] *repl*)
            *repl*])
