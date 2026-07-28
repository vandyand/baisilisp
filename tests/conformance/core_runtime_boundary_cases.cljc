;; Portable clojure.core runtime-boundary semantics for dynamic Vars, Var
;; mutation helpers, bound functions, assertions, agents, taps, and error output.

#?(:clj (require '[clojure.string :as str])
   :lpy (require '[basilisp.string :as str]))

#?(:clj (import '[java.io StringWriter])
   :lpy (import io))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn string-writer []
  #?(:clj (StringWriter.)
     :lpy (io/StringIO)))

(defn writer-value [writer]
  #?(:clj (str writer)
     :lpy (.getvalue writer)))

(defn normalize-newlines [s]
  (str/replace s "\r\n" "\n"))

(def ^:dynamic *runtime-boundary-dynamic* :root)
(def ^:dynamic *runtime-boundary-root* 10)

(emit-case :repl-history-vars-bindable
           (binding [*1 :one
                     *2 :two
                     *3 :three
                     *e :error]
             [*1 *2 *3 *e]))

(emit-case :assert-macro-contract
           {:pass (rejected? #(assert true "ok"))
            :fail (rejected? #(assert false "boom"))
            ;; ``assert`` consults ``*assert*`` while macroexpanding, so an
            ;; ordinary runtime binding around the already-expanded call does
            ;; not suppress the check.
            :runtime-binding-still-checks (binding [*assert* false]
                                             (rejected? #(assert false "still-on")))})

(emit-case :var-root-and-meta-mutation
           (let [a (atom 1 :meta {:a 1})
                 root-ret (alter-var-root #'*runtime-boundary-root* + 3 4)
                 meta-ret (alter-meta! a assoc :b 2)]
             {:root-return root-ret
              :root-value *runtime-boundary-root*
              :meta-return meta-ret
              :meta-value (meta a)}))

(emit-case :bound-fn-dynamic-conveyance
           (let [plain (binding [*runtime-boundary-dynamic* :captured]
                         (bound-fn [] *runtime-boundary-dynamic*))
                 star  (binding [*runtime-boundary-dynamic* :captured-star]
                         (bound-fn* (fn [& xs]
                                      [*runtime-boundary-dynamic* xs])))]
             (binding [*runtime-boundary-dynamic* :caller]
               [(plain) (star 1 2 3)])))

(emit-case :err-writer-and-flush-binding
           (let [writer (string-writer)]
             (binding [*err* writer
                       *flush-on-newline* false]
               (.write *err* "warning"))
             {:err (writer-value writer)
              :out (normalize-newlines
                    (binding [*flush-on-newline* true]
                      (with-out-str (println "visible"))))}))

(emit-case :agent-error-helpers
           (try
             (let [a (agent 0)]
               (send a (fn [_]
                         (throw (ex-info "agent-boom" {:x 1}))))
               (await-for 1000 a)
               (let [error (agent-error a)
                     errors (agent-errors a)
                     before {:state @a
                             :error? (boolean error)
                             :message (ex-message error)
                             :errors-count (count errors)}]
                 (clear-agent-errors a)
                 {:before before
                  :after [(agent-error a) (agent-errors a)]}))
             (finally
               (shutdown-agents))))

(emit-case :tap-delivery-and-removal
           (let [first-seen (promise)
                 second-seen (promise)
                 events (atom [])
                 tap-fn (fn [value]
                          (swap! events conj value)
                          (if (= value :first)
                            (deliver first-seen value)
                            (deliver second-seen value)))]
             (add-tap tap-fn)
             (let [sent-first (tap> :first)
                   delivered-first (deref first-seen 1000 :timeout)
                   _ (remove-tap tap-fn)
                   sent-second (tap> :second)
                   delivered-second (deref second-seen 150 :timeout)]
               {:sent [sent-first sent-second]
                :delivered [delivered-first delivered-second]
                :events @events})))
