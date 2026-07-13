;; Portable queued-sequence behavior. Clojure's process-global Agent executor
;; is shut down only after all observable cases have emitted their values.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(let [queued (seque 2 [1 nil 3])]
  (emit-case :values-and-cache
             {:first-pass (into [] queued)
              :second-pass (into [] queued)}))

(let [values (into [] (seque 2 (lazy-seq
                                 (cons 1
                                       (throw (ex-info "producer failed" {:source :seque}))))))]
  (emit-case :producer-error values))

#?(:clj (shutdown-agents)
   :lpy nil)
