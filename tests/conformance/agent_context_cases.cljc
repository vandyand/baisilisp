;; Portable dynamic-agent-context cases. The differential harness evaluates
;; this exact source in Clojure and Basilisp and compares its EDN output.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(let [a    (agent nil)
      seen (promise)]
  (binding [*agent* :caller]
    (send a (fn [state]
              (deliver seen (identical? a *agent*))
              state)))
  (clojure.core/await a)
  (emit-case :agent-context
             [(nil? *agent*) (deref seen 1000 :timeout)])
  ;; Keep this fixture process self-contained: Clojure's agent executor owns
  ;; non-daemon workers, whereas Basilisp's test process also should release
  ;; its temporary worker resources before exiting.
  (shutdown-agents))
