;; Portable clojure.test.junit/basilisp.test.junit surface and XML helpers.

(ns conformance.junit-cases)

#?(:clj (require '[clojure.test :as t]
                 '[clojure.test.junit :as junit]
                 '[clojure.string :as str])
   :lpy (require '[basilisp.test :as t]
                 '[clojure.test.junit :as junit]
                 '[clojure.string :as str]))

#?(:clj (import '[java.io StringWriter])
   :lpy (import io))

(defn writer []
  #?(:clj (StringWriter.)
     :lpy (io/StringIO)))

(defn writer-str [w]
  #?(:clj (str w)
     :lpy (.getvalue w)))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn pass-sample []
  (t/is (= 2 (+ 1 1)) "pass sample"))

(defn fail-sample []
  (t/is (= 3 (+ 1 1)) "fail sample"))

(defn output-with-depth [depth f]
  (let [w (writer)]
    (binding [t/*test-out* w
              junit/*depth* depth]
      (t/with-test-out (f)))
    (-> (writer-str w)
        (str/replace #"\r\n" "\n"))))

(emit-case :junit-public-surface
           (sort (map name (keys (ns-publics 'clojure.test.junit)))))

(emit-case :junit-package-class
           [(junit/package-class "demo.alpha.Beta")
            (junit/package-class "Beta")
            (junit/suite-attrs "demo.alpha" "Beta")
            (junit/suite-attrs nil "Beta")])

(emit-case :junit-context-and-indentation
           {:var-context-boundary? #?(:clj (some? junit/*var-context*)
                                      :lpy (nil? junit/*var-context*))
            :test-name (junit/test-name [#'pass-sample #'fail-sample])
            :indent-width (count (output-with-depth 2 #(junit/indent)))})

(emit-case :junit-suite-and-case-elements
           (let [suite (output-with-depth
                        1
                        #(do
                           (junit/start-suite "demo.alpha.Beta")
                           (junit/finish-suite)))
                 case (output-with-depth
                       1
                       #(do
                          (junit/start-case "sample" "demo.alpha.Beta")
                          (junit/finish-case)))]
             {:suite (mapv #(str/includes? suite %)
                            ["<testsuite" "name=\"Beta\"" "package=\"demo.alpha\""
                             "</testsuite>"])
              :case (mapv #(str/includes? case %)
                           ["<testcase" "name=\"sample\""
                            "classname=\"demo.alpha.Beta\"" "</testcase>"])}))

(emit-case :junit-xml-escaping
           (let [w (writer)]
             (binding [t/*test-out* w
                       junit/*depth* 1]
               (t/with-test-out
                 (junit/start-element 'sample true {:a "x<y&z" :quote "\"'"})
                 (junit/element-content "body <&> \"'")
                 (junit/finish-element 'sample true)))
             (-> (writer-str w)
                 (str/replace #"\r\n" "\n"))))

(emit-case :junit-message-elements
           (let [message (output-with-depth
                          1
                          #(junit/message-el 'failure "msg <x>" "expected <x>" "actual & y"))
                 failure (output-with-depth
                          1
                          #(junit/failure-el "fail <x>" '(= 1 2) false))
                 error (output-with-depth
                        1
                        #(junit/error-el "err <x>"
                                         '(throw)
                                         #?(:clj (RuntimeException. "boom <xml>")
                                            :lpy (python/RuntimeError "boom <xml>"))))]
             {:message (mapv #(str/includes? message %)
                              ["<failure" "message=\"msg &lt;x&gt;\""
                               "expected: expected &lt;x&gt;"
                               "actual &amp; y"])
              :failure (mapv #(str/includes? failure %)
                              ["<failure" "message=\"fail &lt;x&gt;\""
                               "expected: (= 1 2)" "actual: false"])
              :error (mapv #(str/includes? error %)
                            ["<error" "message=\"err &lt;x&gt;\""
                             "expected: (throw)" "boom &lt;xml&gt;"])}))

(emit-case :with-junit-output-pass
           (let [w (writer)]
             (binding [t/*test-out* w]
               (junit/with-junit-output
                 (t/report {:type :begin-test-ns :ns *ns*})
                 (t/report {:type :begin-test-var :var #'pass-sample})
                 (t/report {:type :pass :message "pass" :expected true :actual true})
                 (t/report {:type :end-test-var :var #'pass-sample})
                 (t/report {:type :end-test-ns :ns *ns*})))
             (-> (writer-str w)
                 (str/replace #"\r\n" "\n"))))

(emit-case :direct-junit-report
           (let [w (writer)
                 counters #?(:clj (ref t/*initial-report-counters*)
                             :lpy (atom t/*initial-report-counters*))]
             (binding [t/*test-out* w
                       t/*report-counters* counters
                       junit/*var-context* (list)
                       junit/*depth* 1]
               (junit/junit-report {:type :begin-test-ns :ns *ns*})
               (junit/junit-report {:type :begin-test-var :var #'pass-sample})
               (junit/junit-report {:type :pass
                                    :message "pass"
                                    :expected true
                                    :actual true})
               (junit/junit-report {:type :end-test-var :var #'pass-sample})
               (junit/junit-report {:type :end-test-ns :ns *ns*})
               (junit/junit-report {:type :default}))
             {:counters @counters
              :output (mapv #(str/includes? (str/replace (writer-str w) #"\r\n" "\n") %)
                             ["<testsuite" "<testcase" "</testcase>" "</testsuite>"])}))
