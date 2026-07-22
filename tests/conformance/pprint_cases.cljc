;; Portable clojure.pprint/basilisp.pprint rendering cases. The fixture
;; compares strings and data-only summaries so host writer classes do not leak
;; into the compatibility boundary.

#?(:clj (require '[clojure.pprint :as pprint]
                 '[clojure.string :as str])
   :lpy (require '[basilisp.pprint :as pprint]
                 '[basilisp.string :as str]))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn normalize-newlines [s]
  (-> s
      (str/replace "\r\n" "\n")
      (str/replace #"[ \t]+\n" "\n")
      (str/replace " \n" "\n")
      str/trim))

(defn rendered [f]
  (normalize-newlines (with-out-str (f))))

(emit-case :basic-rendering
           {:vector (rendered #(pprint/pprint [1 2 (sorted-map :a [3 4] :b [:x :y])]))
            :map-sorted (binding [pprint/*print-right-margin* 18
                                  *print-dup* false]
                          (rendered #(pprint/pprint (sorted-map :a {:c 3}
                                                                :b [1 2]))))
            :length (binding [*print-length* 3]
                      (rendered #(pprint/pprint (range 10))))
            :level (binding [*print-level* 2]
                     (rendered #(pprint/pprint {:a {:b {:c 1}}})))})

(emit-case :code-dispatch
           {:defn (binding [pprint/*print-right-margin* 24]
                    (rendered #(pprint/with-pprint-dispatch pprint/code-dispatch
                                 (pprint/pprint
                                  '(defn add [x y]
                                     (let [sum (+ x y)]
                                       sum))))))
            :case (binding [pprint/*print-right-margin* 24]
                    (rendered #(pprint/with-pprint-dispatch pprint/code-dispatch
                                 (pprint/pprint
                                  '(case command
                                     :start (start-service command)
                                     :stop (stop-service command)
                                     (unknown-command command))))))
            :threading (binding [pprint/*print-right-margin* 24]
                         (rendered #(pprint/with-pprint-dispatch pprint/code-dispatch
                                      (pprint/pprint
                                       '(-> value
                                            (assoc :a 1)
                                            (update :a inc))))))
            :threading-last (binding [pprint/*print-right-margin* 24]
                              (rendered #(pprint/with-pprint-dispatch pprint/code-dispatch
                                           (pprint/pprint
                                            '(->> values
                                                  (filter odd?)
                                                  (map inc))))))
            :threading-some (binding [pprint/*print-right-margin* 24]
                              (rendered #(pprint/with-pprint-dispatch pprint/code-dispatch
                                           (pprint/pprint
                                            '(some-> value
                                                    (assoc :a 1)
                                                    (update :a inc))))))
            :threading-some-last (binding [pprint/*print-right-margin* 24]
                                   (rendered #(pprint/with-pprint-dispatch pprint/code-dispatch
                                                (pprint/pprint
                                                 '(some->> values
                                                          (filter odd?)
                                                          (map inc))))))})

(emit-case :print-table
           {:inferred (rendered #(pprint/print-table [(sorted-map :a 1 :b "two")
                                                      (sorted-map :a 300 :b "four")]))
            :explicit (rendered #(pprint/print-table [:b :a]
                                                     [{:a 1 :b "two"}
                                                      {:a 300 :b "four"}]))
            :empty (rendered #(pprint/print-table [:a :b] []))})

(emit-case :cl-format-core
           {:numbers [(pprint/cl-format nil "~D ~:D ~@D" 12 1234567 12)
                      (pprint/cl-format nil "~,2F" 12.5)
                      (pprint/cl-format nil "~4,'0X" 31)]
            :iteration (pprint/cl-format nil "~{~A~^, ~}" [:a :b :c])
            :conditional (pprint/cl-format nil "~[zero~;one~;two~:;many~]" 3)
            :plural (pprint/cl-format nil "~D file~:P copied" 2)
            :fresh-line (normalize-newlines (pprint/cl-format nil "a~&b~%c"))})

(emit-case :formatter-functions
           (let [to-string (pprint/formatter "x=~D")
                 to-out (pprint/formatter-out "y=~A")]
             {:string (to-string nil 17)
              :out (rendered #(to-out :ok))}))

(def fill-dispatch
  (fn [items]
    (if (vector? items)
      (pprint/pprint-logical-block :prefix "[" :suffix "]"
        (loop [items (seq items)]
          (when items
            (pprint/write-out (first items))
            (when (next items)
              (.write *out* " ")
              (pprint/pprint-newline :fill)
              (recur (next items))))))
      (pr items))))

(emit-case :logical-block-fill
           (binding [pprint/*print-right-margin* 12]
             (rendered #(pprint/with-pprint-dispatch fill-dispatch
                          (pprint/pprint ["aa" "bbb" "cccc" "dd" "eee"])))))
