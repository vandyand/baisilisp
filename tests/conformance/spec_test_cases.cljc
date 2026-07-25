;; Portable clojure.spec.test.alpha / basilisp.spec.test.alpha behavior.
;;
;; The fixture normalizes host-specific generated-check internals and compares
;; only public contracts that both runtimes can represent deterministically.

(require '[clojure.spec.alpha :as s]
         '[clojure.spec.test.alpha :as st])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(def fixture-ns #?(:clj "user" :lpy "basilisp.user"))
(defn fixture-symbol [name] (symbol fixture-ns name))

(def fixture-echo-sym (fixture-symbol "fixture-echo"))
(def fixture-bad-ret-sym (fixture-symbol "fixture-bad-ret"))
(def fixture-related-sym (fixture-symbol "fixture-related"))

(defn fixture-echo [x] x)
(defn fixture-bad-ret [x] "bad")
(defn fixture-related [x] (inc x))

(s/fdef fixture-echo
        :args (s/cat :x int?)
        :ret any?)
(s/fdef fixture-bad-ret
        :args (s/cat :x int?)
        :ret int?)
(s/fdef fixture-related
        :args (s/cat :x int?)
        :ret int?
        :fn (fn [{:keys [args ret]}] (= (inc (:x args)) ret)))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy Exception) _ true)))

(defn failed-result? [result]
  (or (some? (:failure result))
      (some? (:basilisp.spec.test.alpha/failure result))
      (false? (:clojure.spec.test.check/pass? result))
      (false? (:basilisp.spec.test.alpha/pass? result))))

(defn successful-result? [result]
  (and (map? result)
       (not (failed-result? result))))

(defn check-options []
  {:clojure.spec.test.check/opts {:num-tests 5 :seed 7}})

(emit-case :spec-test-public-surface
           (every? #(contains? (ns-publics #?(:clj 'clojure.spec.test.alpha
                                              :lpy 'basilisp.spec.test.alpha))
                               %)
                   '[->sym
                     abbrev-result
                     check
                     check-fn
                     checkable-syms
                     enumerate-namespace
                     instrument
                     instrumentable-syms
                     summarize-results
                     unstrument
                     with-instrument-disabled]))

(emit-case :symbol-and-enumeration-contracts
           {:symbol (= fixture-echo-sym (st/->sym fixture-echo-sym))
            :var (= fixture-echo-sym (st/->sym (resolve fixture-echo-sym)))
            :raw-callable? (ifn? (st/->sym fixture-echo))
            :namespace (contains? (st/enumerate-namespace
                                   #?(:clj 'user :lpy 'basilisp.user))
                                  fixture-echo-sym)
            :namespaces (contains? (st/enumerate-namespace
                                    [#?(:clj 'user :lpy 'basilisp.user)])
                                   fixture-bad-ret-sym)})

(emit-case :discoverability-contracts
           {:checkable (contains? (st/checkable-syms) fixture-echo-sym)
            :checkable-opts (contains? (st/checkable-syms {}) fixture-echo-sym)
            :instrumentable (contains? (st/instrumentable-syms) fixture-echo-sym)
            :instrumentable-opts (contains? (st/instrumentable-syms {})
                                            fixture-echo-sym)})

(emit-case :instrumentation-contracts
           (do
             (st/instrument fixture-echo-sym)
             (let [result {:valid (fixture-echo 1)
                           :invalid-rejected (rejected? #(fixture-echo "x"))
                           :disabled (st/with-instrument-disabled
                                       (fixture-echo "x"))}]
               (st/unstrument fixture-echo-sym)
               (assoc result :unstrumented (fixture-echo "x")))))

(emit-case :check-contracts
           {:single (successful-result?
                     (first (st/check fixture-echo-sym (check-options))))
            :multiple (every? successful-result?
                              (st/check [fixture-echo-sym fixture-related-sym]
                                        (check-options)))
            :ret-failure (failed-result?
                          (first (st/check fixture-bad-ret-sym
                                           (check-options))))})

(emit-case :check-fn-contracts
           {:success (successful-result?
                      (st/check-fn fixture-echo
                                   (s/fspec :args (s/cat :x int?)
                                            :ret any?)
                                   (check-options)))
            :ret-failure (failed-result?
                          (st/check-fn fixture-bad-ret
                                       (s/fspec :args (s/cat :x int?)
                                                :ret int?)
                                       (check-options)))})

(emit-case :summary-and-abbrev-contracts
           (let [summary-result (atom nil)
                 summary (with-out-str
                           (reset! summary-result
                                   (st/summarize-results
                                    [{:sym fixture-echo-sym :failure nil}])))
                 summary-result @summary-result
                 abbrev (st/abbrev-result {:sym fixture-echo-sym
                                           :failure nil})]
             {:summary {:total (:total summary-result)
                        :check-passed (:check-passed summary-result)
                        :printed? (pos? (count summary))}
              :abbrev {:map? (map? abbrev)
                       :sym (= fixture-echo-sym (:sym abbrev))}}))
