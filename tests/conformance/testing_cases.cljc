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

(t/deftest report-counter-assertions
  (t/is true)
  (t/is (odd? 3)))

(def report-counters
  (binding [t/*report-counters* (ref t/*initial-report-counters*)]
    (t/test-var #'report-counter-assertions)
    @t/*report-counters*))

(def equality-return-pairs
  [[0 0]
   [0 1]
   [:same :same]
   [:left :right]
   [[1 2] '(1 2)]
   [{:a 1 :b 2} {:b 2 :a 1}]
   [#{1 2 3} #{3 2 1}]
   [nil nil]
   [nil false]
   [true true]
   [true false]])

(defn equality-return-summary []
  (let [direct [(t/is (= 1 1)) (t/is (= 1 2))]
        seeded (mapv (fn [[left right]]
                        (t/is (= left right)))
                      equality-return-pairs)]
    {:direct direct
     :seeded seeded
     :counters @t/*report-counters*}))

(def equality-return-values
  #?(:clj
     (binding [t/*test-out* (java.io.StringWriter.)
               t/*report-counters* (ref t/*initial-report-counters*)]
       (equality-return-summary))
     :lpy
     (binding [t/*test-output* false
               t/*report-counters* (ref t/*initial-report-counters*)]
       (equality-return-summary))))

(defn thrown-with-msg-return-summary []
  (let [thrown-match (t/is (thrown? #?(:clj Exception :lpy python/Exception)
                                    (throw (#?(:clj Exception.
                                               :lpy python/Exception)
                                            "boom"))))
        thrown-miss  (t/is (thrown? #?(:clj Exception :lpy python/Exception)
                                    42))
        matched   (t/is (thrown-with-msg? #?(:clj Exception :lpy python/Exception)
                                          #"boom"
                                          (throw (#?(:clj Exception.
                                                     :lpy python/Exception)
                                                  "boom"))))
        mismatch  (t/is (thrown-with-msg? #?(:clj Exception :lpy python/Exception)
                                          #"missing"
                                          (throw (#?(:clj Exception.
                                                     :lpy python/Exception)
                                                  "boom"))))
        no-throw  (t/is (thrown-with-msg? #?(:clj Exception :lpy python/Exception)
                                          #"anything"
                                          42))]
    {:returns [(some? thrown-match)
               (nil? thrown-miss)
               (some? matched)
               (some? mismatch)
               (nil? no-throw)]
     :counters @t/*report-counters*}))

(def thrown-with-msg-return-values
  #?(:clj
     (binding [t/*test-out* (java.io.StringWriter.)
               t/*report-counters* (ref t/*initial-report-counters*)]
       (thrown-with-msg-return-summary))
     :lpy
     (binding [t/*test-output* false
               t/*report-counters* (ref t/*initial-report-counters*)]
       (thrown-with-msg-return-summary))))

#?(:clj (binding [t/*test-out* (java.io.StringWriter.)]
          (t/test-ns 'conformance.testing-cases))
   :lpy (binding [t/*test-output* false]
          (t/test-ns 'conformance.testing-cases)))

(emit-case :assertions-and-fixtures @fixture-events)
(emit-case :test-var-report-counters report-counters)
(emit-case :is-equality-return-values equality-return-values)
(emit-case :thrown-with-msg-return-values thrown-with-msg-return-values)
