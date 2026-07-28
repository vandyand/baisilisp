;; Final portable clojure.core residuals: ResultSet/DB cursor row projection
;; and syntax quote unquote/unquote-splicing behavior. JDBC ResultSet and
;; Python DB-API cursor construction are host-specific; emitted rows are
;; normalized to stable data.

#?(:clj (import '[javax.sql.rowset RowSetProvider RowSetMetaDataImpl]
                'java.sql.Types)
   :lpy (import sqlite3))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

#?(:clj
   (defn make-result-set [labels rows]
     (let [metadata (RowSetMetaDataImpl.)
           result-set (.createCachedRowSet (RowSetProvider/newFactory))]
       (.setColumnCount metadata (count labels))
       (doseq [[index label] (map-indexed vector labels)]
         (.setColumnName metadata (inc index) label)
         (.setColumnLabel metadata (inc index) label)
         (.setColumnType metadata (inc index) Types/VARCHAR))
       (.setMetaData result-set metadata)
       (doseq [row rows]
         (.moveToInsertRow result-set)
         (doseq [[index value] (map-indexed vector row)]
           (.updateObject result-set (inc index) value))
         (.insertRow result-set)
         (.moveToCurrentRow result-set))
       (.beforeFirst result-set)
       result-set))
   :lpy
   (defn make-result-set [labels rows]
     (let [connection (.connect sqlite3 ":memory:")
           cursor (.cursor connection)
           columns (map-indexed (fn [index label]
                                  (str "c" index " text"))
                                labels)]
       (.execute cursor (str "create table rows ("
                             (if (seq columns)
                               (apply str (interpose "," columns))
                               "placeholder text")
                             ")"))
       (doseq [row rows]
         (if (seq labels)
           (let [placeholders (apply str (interpose "," (repeat (count labels) "?")))]
             (.execute cursor
                       (str "insert into rows values (" placeholders ")")
                       (python/tuple row)))
           (.execute cursor "insert into rows values ('placeholder')")))
       (.execute cursor
                 (if (seq labels)
                   (str "select "
                        (apply str
                               (interpose
                                ","
                                (map-indexed (fn [index label]
                                               (str "c" index " as " label))
                                             labels)))
                        " from rows")
                   "select placeholder from rows where 1 = 0"))
       cursor)))

(defn close-result-set [result-set]
  (try
    #?(:clj (.close result-set)
       :lpy (do
              (some-> (.-connection result-set) (.close))
              (.close result-set)))
    (catch #?(:clj Throwable :lpy python/Exception) _
      nil)))

(defn rows-summary [labels rows]
  (let [result-set (make-result-set labels rows)]
    (try
      (sort-by :id (mapv identity (resultset-seq result-set)))
      (finally
        (close-result-set result-set)))))

(defn normalize-syntax-form [form]
  (cond
    (symbol? form) (symbol (name form))
    (seq? form) (mapv normalize-syntax-form form)
    (vector? form) (mapv normalize-syntax-form form)
    :else form))

(emit-case :resultset-seq-row-projection
           {:basic (rows-summary ["ID" "Name"]
                                 [["2" "Grace"]
                                  ["1" "Ada"]])
            :case-normalization (rows-summary ["ID" "Display_Name"]
                                             [["7" "Lin"]])})

(emit-case :resultset-seq-rejection-and-fuzz
           {:duplicate-labels (let [result-set (make-result-set ["ID" "id"]
                                                               [["1" "2"]])]
                                (try
                                  (rejected? #(resultset-seq result-set))
                                  (finally
                                    (close-result-set result-set))))
            :seeded (mapv (fn [n]
                            (rows-summary ["ID" "Value" "Parity"]
                                          [[(str n)
                                            (str (* n n))
                                            (if (even? n) "even" "odd")]
                                           [(str (+ n 10))
                                            (str (* (+ n 10) (+ n 10)))
                                            (if (even? n) "even+" "odd+")]]))
                          (range 5))})

(emit-case :syntax-unquote-contracts
           (let [x 10
                 xs [1 2 3]]
             {:unquote-symbol (quote unquote)
              :unquote-splicing-symbol (quote unquote-splicing)
              :unquote-result (= '[alpha 10 omega]
                                 (normalize-syntax-form `(alpha ~x omega)))
              :unquote-splicing-result (= '[alpha 1 2 3 omega]
                                          (normalize-syntax-form
                                           `(alpha ~@xs omega)))
              :nested (let [form `(outer ~(list 'inner x) ~@xs)]
                        (= '[outer [inner 10] 1 2 3]
                           (normalize-syntax-form form)))}))
