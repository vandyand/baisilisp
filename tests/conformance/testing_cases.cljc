;; Portable clojure.test / basilisp.test macro and fixture behavior. Reporter
;; implementation details intentionally stay outside this shared contract.

(ns conformance.testing-cases)

#?(:clj (require '[clojure.test :as t])
   :lpy (require '[basilisp.test :as t]))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(def fixture-events (atom []))

(t/use-fixtures :each
  (fn [run-test]
    (swap! fixture-events conj :before)
    (run-test)
    (swap! fixture-events conj :after)))

(t/deftest portable-assertions
  (t/testing "ordinary assertions"
    (t/is (= 3 (+ 1 2)))
    (t/are [expected actual] (= expected actual)
      2 (+ 1 1)
      4 (* 2 2))))

#?(:clj (binding [t/*test-out* (java.io.StringWriter.)]
          (t/test-ns 'conformance.testing-cases))
   :lpy (binding [t/*test-output* false]
          (t/test-ns 'conformance.testing-cases)))

(emit-case :assertions-and-fixtures @fixture-events)
