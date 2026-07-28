;; Portable clojure.core lifecycle/runtime helper semantics. Host-specific
;; namespace, future, and protocol objects are normalized to booleans, names,
;; counts, or ordinary values before comparison.

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(def ^:dynamic *lifecycle-dynamic* :root)

(defn binding-summary []
  (binding [*lifecycle-dynamic* :bound]
    (let [bindings (get-thread-bindings)]
      {:map? (map? bindings)
       :contains? (contains? bindings #'*lifecycle-dynamic*)
       :value (get bindings #'*lifecycle-dynamic*)})))

(emit-case :default-data-readers-portable-surface
           {:map? (map? default-data-readers)
            :standard-readers (mapv #(contains? default-data-readers %)
                                    ['inst 'uuid])
            :reader-count-at-least-standard (>= (count default-data-readers) 2)})

(emit-case :namespace-lifecycle-and-var-lookup
           (let [ns-sym (symbol (str "parity.lifecycle." (gensym)))
                 alias-sym (symbol (str "pl" (gensym)))
                 created (create-ns ns-sym)
                 interned (intern created 'x 42)
                 _ (alias alias-sym ns-sym)
                 found (find-var (symbol (str ns-sym) "x"))]
             (try
               {:created (= (str ns-sym) (str (ns-name created)))
                :all-ns? (boolean (some #(= (str ns-sym) (str (ns-name %)))
                                        (all-ns)))
                :alias? (contains? (ns-aliases *ns*) alias-sym)
                :interned? (boolean interned)
                :found? (boolean found)
                :found-value @found}
               (finally
                 (ns-unalias *ns* alias-sym)
                 (remove-ns ns-sym)))))

(emit-case :thread-bindings-delay-and-force
           {:bindings (binding-summary)
            :delay [(delay? (delay :value))
                    (delay? :value)
                    (let [forced (delay :forced)]
                      [(realized? forced)
                       (force forced)
                       (realized? forced)])
                    (force :plain)]})

(emit-case :future-lifecycle-helpers
           (let [called (atom [])
                 f (future-call (fn []
                                  (swap! called conj :future-call)
                                  42))
                 g (future
                     (swap! called conj :future-macro)
                     7)
                 values [@f @g]]
             {:values values
              :called @called
              :states [(future? f)
                       (future? g)
                       (future-done? f)
                       (future-done? g)
                       (future-cancelled? f)
                       (future-cancel f)
                       (future-cancelled? f)]}))

(emit-case :agent-mode-and-handler-helpers
           (try
             (let [events (atom [])
                   handler (fn [agent error]
                             (swap! events conj [(error-mode agent)
                                                 (ex-message error)]))
                   a (agent 0 :error-mode :continue :error-handler handler)]
               (send a (fn [_] (throw (ex-info "continue-boom" {}))))
               (await-for 1000 a)
               {:state @a
                :mode (error-mode a)
                :handler? (identical? handler (error-handler a))
                :error? (boolean (agent-error a))
                :events @events})
             (finally
               (shutdown-agents))))

(defprotocol LifecycleProtocol
  (lifecycle-value [this]))

(extend nil
  LifecycleProtocol
  {:lifecycle-value (fn [_] :nil-impl)})

(emit-case :nil-protocol-extension-helpers
           {:call (lifecycle-value nil)
            :extends (extends? LifecycleProtocol nil)
            :extenders-count (count (extenders LifecycleProtocol))
            :impl? (boolean (find-protocol-impl LifecycleProtocol nil))
            :method? (boolean (find-protocol-method LifecycleProtocol
                                                    :lifecycle-value
                                                    nil))})
