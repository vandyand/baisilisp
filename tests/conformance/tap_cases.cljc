;; Portable clojure.test.tap/basilisp.test.tap cases. TAP report output is
;; captured through clojure.test/*test-out* because Clojure's reporter writes
;; with clojure.test/with-test-out rather than ordinary *out* capture.

#?(:clj (require '[clojure.string :as str]
                 '[clojure.test :as t]
                 '[clojure.test.tap :as tap])
   :lpy (require '[basilisp.string :as str]
                 '[basilisp.test :as t]
                 '[basilisp.test.tap :as tap]))

#?(:clj (import 'java.io.StringWriter)
   :lpy (import io))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn normalize-newlines [s]
  (-> s
      (str/replace "\r\n" "\n")
      (str/replace #"[ \t]+\n" "\n")))

(defn capture-out [f]
  (normalize-newlines (with-out-str (f))))

(defn capture-test-out [f]
  #?(:clj (let [w (StringWriter.)]
            (binding [t/*test-out* w]
              (f))
            (normalize-newlines (str w)))
     :lpy (let [w (io/StringIO)]
            (binding [t/*test-out* w]
              (f))
            (normalize-newlines (.getvalue w)))))

(defn public-tap-names []
  (sort (map name (keys (ns-publics #?(:clj 'clojure.test.tap
                                        :lpy 'basilisp.test.tap))))))

(def pass-report
  {:type :pass
   :message "pass message"
   :expected '(= 1 1)
   :actual '(= 1 1)})

(def fail-report
  {:type :fail
   :message "fail message"
   :expected '(= 1 2)
   :actual '(not (= 1 2))})

(emit-case :public-surface
           (public-tap-names))

(emit-case :direct-printers
           {:plan (capture-out #(tap/print-tap-plan 3))
            :pass (capture-out #(tap/print-tap-pass "direct pass"))
            :fail (capture-out #(tap/print-tap-fail "direct fail"))
            :diagnostic (capture-out #(tap/print-tap-diagnostic "first\nsecond"))})

(emit-case :print-diagnostics
           {:pass (capture-out #(tap/print-diagnostics pass-report))
            :fail (capture-out #(tap/print-diagnostics fail-report))})

(emit-case :tap-report
           {:pass (capture-test-out #(tap/tap-report pass-report))
            :fail (capture-test-out #(tap/tap-report fail-report))
            :summary (capture-test-out #(tap/tap-report {:type :summary
                                                         :pass 1
                                                         :fail 1
                                                         :error 1}))
            :default (capture-test-out #(tap/tap-report (sorted-map :type :custom
                                                                     :value [1 2 3])))})

(emit-case :with-tap-output-binding
           (let [original t/report]
             (tap/with-tap-output
              (= t/report tap/tap-report))))

(emit-case :seeded-diagnostics
           (mapv (fn [n]
                   (let [report {:type (if (even? n) :pass :fail)
                                 :message (str "msg-" n)
                                 :expected (list '= n n)
                                 :actual (if (even? n)
                                           (list '= n n)
                                           (list 'not (list '= n (inc n))))}]
                     (capture-out #(tap/print-diagnostics report))))
                 (range 24)))
