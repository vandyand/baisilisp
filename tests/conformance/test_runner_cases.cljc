;; Portable clojure.test runner/helper contracts.
;;
;; This fixture compares data-shaped runner behavior and report hooks, not host
;; renderer text or exception class names.

(ns conformance.test-runner-cases)

#?(:clj (require '[clojure.test :as t])
   :lpy (require '[basilisp.test :as t]))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn quiet [f]
  #?(:clj (binding [t/*test-out* (java.io.StringWriter.)] (f))
     :lpy (binding [t/*test-output* false] (f))))

#?(:lpy
   (def extension-touch
     [t/*test-name*
      t/*test-section*
      t/*test-failures*
      t/*test-passes*
      t/*test-line*
      t/*test-results*
      t/fixture-takes-thunk?
      t/generator?
      t/gen-assert
      t/record-report!
      t/with-fixtures])
   :clj
   (def extension-touch nil))

(defn helper-fn [] :ok)
(def bound-value 42)
(def events (atom []))

(defmethod t/report :conformance/event [m]
  (swap! events conj {:type (:type m)
                      :payload (:payload m)
                      :contexts (vec t/*testing-contexts*)}))

(t/deftest pass-a
  (t/is true)
  (t/is (= 1 1)))

(t/deftest fail-a
  (t/is false))

(t/deftest error-a
  (throw (ex-info "runner error" {:source :runner})))

(t/deftest- private-a
  (t/is true))

(t/with-test (defn with-tested [] :value)
  (t/is (= :value (with-tested))))

(defn set-tested [] :set-value)

(t/set-test set-tested
  (t/is (= :set-value (set-tested))))

(emit-case :dynamic-vars-and-helpers
           {:load-tests t/*load-tests*
            :stack-depth-nil (nil? t/*stack-trace-depth*)
            :testing-contexts (vec t/*testing-contexts*)
            :testing-vars (vec t/*testing-vars*)
            :initial-counters t/*initial-report-counters*
            :test-out-present (some? t/*test-out*)
            :get-possibly-unbound-var (t/get-possibly-unbound-var #'bound-value)
            :function? [(t/function? helper-fn)
                        (t/function? 'helper-fn)]
            :file-position (let [[file line] (t/file-position 0)]
                             [(string? file) (integer? line)])
            :assert-code [(boolean (t/assert-any "message" 'true))
                          (boolean (t/assert-predicate "message" '(pos? 1)))]})

(emit-case :fixture-composition
           (let [fixture-events (atom [])
                 f1 (fn [run]
                      (swap! fixture-events conj :f1-before)
                      (run)
                      (swap! fixture-events conj :f1-after))
                 f2 (fn [run]
                      (swap! fixture-events conj :f2-before)
                      (run)
                      (swap! fixture-events conj :f2-after))]
             (let [joined (t/join-fixtures [f1 f2])
                   composed (t/compose-fixtures f1 f2)]
               (joined #(swap! fixture-events conj :joined-body))
               (composed #(swap! fixture-events conj :composed-body))
               @fixture-events)))

(emit-case :reporting-and-counters
           (let [counters (binding [t/*report-counters*
                                    (ref t/*initial-report-counters*)]
                            (t/inc-report-counter :pass)
                            (t/inc-report-counter :fail)
                            @t/*report-counters*)]
             (reset! events [])
             (t/do-report {:type :conformance/event :payload :via-do-report})
             (t/report {:type :conformance/event :payload :via-report})
             {:counters counters
              :events @events}))

(emit-case :assertion-generation
           (let [counters (binding [t/*report-counters*
                                    (ref t/*initial-report-counters*)]
                            (t/try-expr "truthy" true)
                            @t/*report-counters*)]
             {:try-expr counters
              :successful [(t/successful? {:fail 0 :error 0})
                           (t/successful? {:fail 1 :error 0})
                           (t/successful? {:fail 0 :error 1})]}))

(emit-case :metadata-backed-tests
           {:deftest-private (true? (:private (meta #'private-a)))
            :with-test (ifn? (:test (meta #'with-tested)))
            :set-test (ifn? (:test (meta #'set-tested)))})

(emit-case :context-strings
           {:contexts (t/testing "outer"
                       (t/testing "inner"
                         (t/testing-contexts-str)))
            :vars (binding [t/*testing-vars* [#'pass-a]]
                    (t/testing-vars-str {:line 7}))})

(emit-case :low-level-runner-returns
           {:test-vars (nil? (quiet #(t/test-vars [#'pass-a])))
            :test-all-vars (nil? (quiet #(t/test-all-vars 'conformance.test-runner-cases)))
            :test-ns (quiet #(t/test-ns 'conformance.test-runner-cases))})

(emit-case :summary-runners
           {:run-test-var (quiet #(t/run-test-var #'pass-a))
            :run-test (quiet #(t/run-test pass-a))
            :run-tests (quiet #(t/run-tests 'conformance.test-runner-cases))
            :run-all-tests (quiet #(t/run-all-tests
                                    #"conformance\.test-runner-cases"))})

(def hook-events (atom []))

(t/deftest hook-target
  (swap! hook-events conj :hook-target)
  (t/is true))

(defn test-ns-hook []
  (hook-target))

(emit-case :test-ns-hook-direct-calls
           (let [summary (quiet #(t/run-tests 'conformance.test-runner-cases))]
             {:events @hook-events
              :summary summary}))
