(ns acceptance.portable-library.checks
  #?(:clj (:require [clojure.test :as t]
                    [acceptance.portable-library.catalog :as catalog])
     :lpy (:require [basilisp.test :as t]
                    [acceptance.portable-library.catalog :as catalog])))

(t/deftest catalog-summary-test
  (let [summary (catalog/summarize [{:id " Alpha " :title "First"}
                                    {:id "BETA" :title "Second"}]
                                   #{"beta"})]
    (t/is (= #{"alpha"} (:ids summary)))
    (t/is (= {:alpha "First" :beta "Second"} (:titles summary)))
    (t/is (= ["FIRST"] (:visible-titles summary)))
    (t/is (= 2 (:entry-count summary)))))

(t/deftest payload-decoding-test
  (t/is (= {:outer {:inner 1} :already :kept}
           (catalog/decode-payload {"outer" {"inner" 1} :already :kept})))
  (t/is (= {:value [:not :a :map]}
           (try
             (catalog/decode-payload [:not :a :map])
             :did-not-throw
             (catch Exception error
               (ex-data error))))))

(defn acceptance-summary []
  (t/run-tests 'acceptance.portable-library.checks))
