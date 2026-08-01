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

(defn equality-arity-report-body []
  (let [events (atom [])
        event-summary (fn [m]
                        {:type (:type m)
                         :message (:message m)
                         :expected (pr-str (:expected m))
                         :actual (if (= :error (:type m))
                                   :exception
                                   (pr-str (:actual m)))})
        capture-report (fn [m]
                         (swap! events conj (event-summary m))
                         nil)]
    #?(:clj
       (with-redefs [t/report capture-report]
         {:returns [(t/is (=) "zero")
                    (t/is (= 1) "one")
                    (t/is (= 1 1 1 1) "many-pass")
                    (t/is (= 1 1 2 1) "many-fail")
                    (t/is (= :a :a :a) "keywords")
                    (t/is (= [:a 1] [:a 1] '(:a 2)) "sequential-fail")]
          :events @events})
       :lpy
       (binding [t/report capture-report]
         {:returns [(t/is (=) "zero")
                    (t/is (= 1) "one")
                    (t/is (= 1 1 1 1) "many-pass")
                    (t/is (= 1 1 2 1) "many-fail")
                    (t/is (= :a :a :a) "keywords")
                    (t/is (= [:a 1] [:a 1] '(:a 2)) "sequential-fail")]
          :events @events}))))

(def equality-arity-report-values
  #?(:clj
     (binding [t/*test-out* (java.io.StringWriter.)]
       (equality-arity-report-body))
     :lpy
     (binding [t/*test-output* false]
       (equality-arity-report-body))))

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

(defn exception-report-expected-thrown? [m class-symbol body-summary]
  (let [form (:expected m)]
    (and (seq? form)
         (= 'thrown? (first form))
         (= 3 (count form))
         (= class-symbol (second form))
         (= body-summary (pr-str (nth form 2))))))

(defn exception-report-expected-thrown-with-msg? [m class-symbol pattern body-summary]
  (let [form (:expected m)]
    (and (seq? form)
         (= 'thrown-with-msg? (first form))
         (= 4 (count form))
         (= class-symbol (second form))
         (= pattern (pr-str (nth form 2)))
         (= body-summary (pr-str (nth form 3))))))

(defn exception-report-expected-matches? [m]
  (let [exception-symbol #?(:clj 'Exception :lpy 'python/Exception)
        wrong-symbol #?(:clj 'IllegalArgumentException :lpy 'python/ValueError)
        throw-body #?(:clj "(throw (Exception. \"boom\"))"
                      :lpy "(throw (python/Exception \"boom\"))")]
    (case (:message m)
      "thrown-pass" (exception-report-expected-thrown? m exception-symbol throw-body)
      "thrown-no" (exception-report-expected-thrown? m exception-symbol "42")
      "thrown-wrong" (exception-report-expected-thrown? m wrong-symbol throw-body)
      "msg-pass" (exception-report-expected-thrown-with-msg? m exception-symbol
                                                            "#\"boom\""
                                                            throw-body)
      "msg-mismatch" (exception-report-expected-thrown-with-msg? m exception-symbol
                                                                "#\"missing\""
                                                                throw-body)
      "msg-no" (exception-report-expected-thrown-with-msg? m exception-symbol
                                                          "#\"anything\""
                                                          "42")
      "msg-wrong" (exception-report-expected-thrown-with-msg? m wrong-symbol
                                                             "#\"boom\""
                                                             throw-body))))

(defn exception-report-actual-kind [actual]
  (cond
    #?(:clj (instance? Throwable actual)
       :lpy (instance? python/BaseException actual)) :exception
    (nil? actual) :nil
    :else :value))

(defn exception-report-actual-summary [actual]
  (cond
    #?(:clj (instance? Throwable actual)
       :lpy (instance? python/BaseException actual)) #?(:clj (.getMessage actual)
                                                        :lpy (python/str actual))
    :else (pr-str actual)))

(defn exception-report-summary [m]
  {:type (:type m)
   :message (:message m)
   :expected-matches-source (exception-report-expected-matches? m)
   :actual-kind (exception-report-actual-kind (:actual m))
   :actual (exception-report-actual-summary (:actual m))})

(defn exception-report-payload-body []
  (let [events (atom [])
        capture-report (fn [m]
                         (swap! events conj (exception-report-summary m))
                         nil)]
    #?(:clj
       (with-redefs [t/report capture-report]
         (t/is (thrown? Exception
                        (throw (Exception. "boom")))
               "thrown-pass")
         (t/is (thrown? Exception 42)
               "thrown-no")
         (t/is (thrown? IllegalArgumentException
                        (throw (Exception. "boom")))
               "thrown-wrong")
         (t/is (thrown-with-msg? Exception
                                 #"boom"
                                 (throw (Exception. "boom")))
               "msg-pass")
         (t/is (thrown-with-msg? Exception
                                 #"missing"
                                 (throw (Exception. "boom")))
               "msg-mismatch")
         (t/is (thrown-with-msg? Exception
                                 #"anything"
                                 42)
               "msg-no")
         (t/is (thrown-with-msg? IllegalArgumentException
                                 #"boom"
                                 (throw (Exception. "boom")))
               "msg-wrong")
         @events)
       :lpy
       (binding [t/report capture-report]
         (t/is (thrown? python/Exception
                        (throw (python/Exception "boom")))
               "thrown-pass")
         (t/is (thrown? python/Exception 42)
               "thrown-no")
         (t/is (thrown? python/ValueError
                        (throw (python/Exception "boom")))
               "thrown-wrong")
         (t/is (thrown-with-msg? python/Exception
                                 #"boom"
                                 (throw (python/Exception "boom")))
               "msg-pass")
         (t/is (thrown-with-msg? python/Exception
                                 #"missing"
                                 (throw (python/Exception "boom")))
               "msg-mismatch")
         (t/is (thrown-with-msg? python/Exception
                                 #"anything"
                                 42)
               "msg-no")
         (t/is (thrown-with-msg? python/ValueError
                                 #"boom"
                                 (throw (python/Exception "boom")))
               "msg-wrong")
         @events))))

(def exception-report-payload-values
  #?(:clj
     (binding [t/*test-out* (java.io.StringWriter.)]
       (exception-report-payload-body))
     :lpy
     (binding [t/*test-output* false]
       (exception-report-payload-body))))

(defn instance-report-actual-summary [actual]
  (cond
    #?(:clj (= String actual)
       :lpy (= python/str actual)) :string-class
    #?(:clj (= Long actual)
       :lpy (= python/int actual)) :integer-class
    (nil? actual) :nil
    :else (pr-str actual)))

(defn instance-report-expected-matches? [m]
  (let [string-symbol #?(:clj 'String :lpy 'python/str)]
    (case (:message m)
      "instance-pass" (= (:expected m)
                         (list 'instance? string-symbol "x"))
      "instance-fail" (= (:expected m)
                         (list 'instance? string-symbol 1))
      "instance-nil" (= (:expected m)
                        (list 'instance? string-symbol nil))
      "predicate-fail" (= (:expected m) '(string? 1)))))

(defn instance-report-summary [m]
  {:type (:type m)
   :message (:message m)
   :expected-matches-source (instance-report-expected-matches? m)
   :actual (if (= "predicate-fail" (:message m))
             (pr-str (:actual m))
             (instance-report-actual-summary (:actual m)))})

(defn instance-report-payload-body []
  (let [events (atom [])
        capture-report (fn [m]
                         (swap! events conj (instance-report-summary m))
                         nil)]
    #?(:clj
       (with-redefs [t/report capture-report]
         {:returns [(t/is (instance? String "x") "instance-pass")
                    (t/is (instance? String 1) "instance-fail")
                    (t/is (instance? String nil) "instance-nil")
                    (t/is (string? 1) "predicate-fail")]
          :events @events})
       :lpy
       (binding [t/report capture-report]
         {:returns [(t/is (instance? python/str "x") "instance-pass")
                    (t/is (instance? python/str 1) "instance-fail")
                    (t/is (instance? python/str nil) "instance-nil")
                    (t/is (string? 1) "predicate-fail")]
          :events @events}))))

(def instance-report-payload-values
  #?(:clj
     (binding [t/*test-out* (java.io.StringWriter.)]
       (instance-report-payload-body))
     :lpy
     (binding [t/*test-output* false]
       (instance-report-payload-body))))

(defn qualified-report-head-symbols []
  {:eq #?(:clj 'clojure.core/= :lpy 'basilisp.core/=)
   :instance #?(:clj 'clojure.core/instance? :lpy 'basilisp.core/instance?)
   :not #?(:clj 'clojure.core/not :lpy 'basilisp.core/not)})

(defn qualified-report-expected-matches? [m]
  (let [{eq-symbol :eq instance-symbol :instance not-symbol :not}
        (qualified-report-head-symbols)]
    (case (:message m)
      "fq-eq" (= (:expected m) (list eq-symbol 1 2))
      "fq-instance-pass" (= (:expected m)
                            (list instance-symbol
                                  #?(:clj 'String :lpy 'python/str)
                                  "x"))
      "fq-instance-fail" (= (:expected m)
                            (list instance-symbol
                                  #?(:clj 'String :lpy 'python/str)
                                  1))
      "fq-not" (= (:expected m) (list not-symbol true)))))

(defn qualified-report-generic-actual? [m]
  (let [{eq-symbol :eq instance-symbol :instance not-symbol :not}
        (qualified-report-head-symbols)
        actual (:actual m)]
    (case (:message m)
      "fq-eq" (and (seq? actual)
                   (= 'not (first actual))
                   (= (list eq-symbol 1 2) (second actual)))
      "fq-instance-pass" (and (seq? actual)
                              (= instance-symbol (first actual))
                              (= :string-class (instance-report-actual-summary (second actual)))
                              (= "x" (nth actual 2)))
      "fq-instance-fail" (let [inner (second actual)]
                           (and (seq? actual)
                                (= 'not (first actual))
                                (seq? inner)
                                (= instance-symbol (first inner))
                                (= :string-class
                                   (instance-report-actual-summary (second inner)))
                                (= 1 (nth inner 2))))
      "fq-not" (and (seq? actual)
                    (= 'not (first actual))
                    (= (list not-symbol true) (second actual))))))

(defn qualified-report-summary [m]
  {:type (:type m)
   :message (:message m)
   :expected-matches-source (qualified-report-expected-matches? m)
   :actual-is-generic-predicate (qualified-report-generic-actual? m)})

(defn qualified-report-payload-body []
  (let [events (atom [])
        capture-report (fn [m]
                         (swap! events conj (qualified-report-summary m))
                         nil)]
    #?(:clj
       (with-redefs [t/report capture-report]
         {:returns [(t/is (clojure.core/= 1 2) "fq-eq")
                    (t/is (clojure.core/instance? String "x") "fq-instance-pass")
                    (t/is (clojure.core/instance? String 1) "fq-instance-fail")
                    (t/is (clojure.core/not true) "fq-not")]
          :events @events})
       :lpy
       (binding [t/report capture-report]
         {:returns [(t/is (basilisp.core/= 1 2) "fq-eq")
                    (t/is (basilisp.core/instance? python/str "x") "fq-instance-pass")
                    (t/is (basilisp.core/instance? python/str 1) "fq-instance-fail")
                    (t/is (basilisp.core/not true) "fq-not")]
          :events @events}))))

(def qualified-report-payload-values
  #?(:clj
     (binding [t/*test-out* (java.io.StringWriter.)]
       (qualified-report-payload-body))
     :lpy
     (binding [t/*test-output* false]
       (qualified-report-payload-body))))

(defn macroexpands? [form]
  (try
    (macroexpand form)
    true
    (catch #?(:clj Throwable :lpy python/Exception) _
      false)))

(def are-value-count-boundary-values
  {:zero-bindings-no-values (macroexpands? '(t/are [] true))
   :zero-bindings-extra-value (macroexpands? '(t/are [] true 1))
   :one-binding-no-values (macroexpands? '(t/are [x] (= x x)))
   :one-binding-one-value (macroexpands? '(t/are [x] (= x x) 1))
   :two-bindings-short-row (macroexpands? '(t/are [x y] (= x y) 1))
   :two-bindings-trailing-value (macroexpands? '(t/are [x y] (= x y) 1 1 2))})

#?(:clj (binding [t/*test-out* (java.io.StringWriter.)]
          (t/test-ns 'conformance.testing-cases))
   :lpy (binding [t/*test-output* false]
          (t/test-ns 'conformance.testing-cases)))

(emit-case :assertions-and-fixtures @fixture-events)
(emit-case :test-var-report-counters report-counters)
(emit-case :is-equality-return-values equality-return-values)
(emit-case :is-equality-arity-report-values equality-arity-report-values)
(emit-case :thrown-with-msg-return-values thrown-with-msg-return-values)
(emit-case :exception-report-payload-values exception-report-payload-values)
(emit-case :instance-report-payload-values instance-report-payload-values)
(emit-case :qualified-report-payload-values qualified-report-payload-values)
(emit-case :are-value-count-boundary-values are-value-count-boundary-values)
