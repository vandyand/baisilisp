;; Compare public assertion report fields without relying on host exception
;; class names or renderer text.

(ns conformance.testing-reporting-cases)

#?(:clj (require '[clojure.test :as t])
   :lpy (require '[basilisp.test :as t]))

(def events (atom []))
(def fixture-events (atom []))

(t/use-fixtures :each
  (fn [run-test]
    (swap! fixture-events conj :before)
    (run-test)
    (swap! fixture-events conj :after)))

(defmethod t/assert-expr 'is-even? [msg form]
  `(let [value# ~(second form)]
     (t/do-report {:type (if (even? value#) :pass :fail)
                   :message ~msg
                   :expected :even
                   :actual value#})))

(defn throwable-summary [exception]
  {:message (ex-message exception)
   :data (ex-data exception)})

(defn normalized-event [m]
  {:type (:type m)
   :message (:message m)
   :expected (:expected m)
   :actual (if (= :error (:type m))
             (throwable-summary (:actual m))
             (:actual m))
   :contexts #?(:clj (vec t/*testing-contexts*)
                :lpy (vec t/*testing-contexts*))})

(defmethod t/report :pass [m]
  (swap! events conj (normalized-event m)))

(defmethod t/report :fail [m]
  (swap! events conj (normalized-event m)))

(defmethod t/report :error [m]
  (swap! events conj (normalized-event m)))

(defmethod t/report :summary [_] nil)

(t/deftest reporting-shape
  (t/testing "outer"
    (t/is (= 2 (+ 1 1)) "equal pass")
    (t/testing "inner"
      (t/is false "truthy failure")
      (t/is (is-even? 4) "custom assertion")
      (t/is (throw (ex-info "reporting error" {:source :reporting}))
            "error event"))))

#?(:clj (binding [t/*test-out* (java.io.StringWriter.)]
          (t/test-ns 'conformance.testing-reporting-cases))
   :lpy (binding [t/*test-output* false]
          (t/test-ns 'conformance.testing-reporting-cases)))

(println (pr-str {:case :reporting-events
                  :value {:events @events :fixtures @fixture-events}}))
