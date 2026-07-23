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

(defn rendered-code [margin form]
  (binding [pprint/*print-right-margin* margin]
    (rendered #(pprint/with-pprint-dispatch pprint/code-dispatch
                 (pprint/pprint form)))))

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

(let [cases [[24 '(def very-long-name (+ 1 2 3))]
             [24 '(defonce cached-value (delay (expensive-call input)))]
             [24 '(if-not (very-long-predicate alpha beta)
                    (then-branch alpha)
                    (else-branch beta))]
             [24 '(when-not (ready? system)
                    (start! system)
                    (await-ready))]
             [24 '(condp = command
                    :start :started
                    :stop :stopped
                    :restart :restarted
                    :unknown)]
             [24 '(with-local-vars [x 1 y (+ x 2)]
                    (+ @x @y))]
             [24 '(. target method arg1 arg2)]
             [24 '(.. target (first-call alpha) (second-call beta))]
             [24 '(locking lock
                    (mutate! state)
                    (snapshot state))]
             [24 '(struct-map basis :a 1 :b 2)]
             [24 '(fn* [x] (+ x 1))]
             [24 '(fn* [x y] (+ x y))]
             [18 '(if (small? x) :small :large)]
             [18 '(when ready? (run-one) (run-two))]
             [40 '(def short-name value)]]]
  (emit-case :code-dispatch-table-families
             (mapv (fn [[margin form]]
                     [margin (rendered-code margin form)])
                   cases)))

(defn generated-code-form [i]
  (case (mod i 10)
    0 (list 'def (symbol (str "generated-value-" i)) (list '+ i (inc i)))
    1 (list 'defonce (symbol (str "generated-delay-" i)) (list '+ i 1))
    2 (list 'if (list 'pred? (symbol (str "x" i)))
            (list 'then-branch i)
            (list 'else-branch (inc i)))
    3 (list 'if-not (list 'pred? (symbol (str "x" i)))
            (list 'fallback i)
            (list 'success (inc i)))
    4 (list 'when (list 'ready? i)
            :step-one
            :step-two)
    5 (list 'when-not (list 'ready? i)
            :recover
            :retry)
    6 (list 'condp '= (symbol (str "command" i))
            :a :alpha
            :b :beta
            :default)
    7 (list 'locking (symbol (str "lock" i))
            (list 'mutate! i)
            (list 'snapshot i))
    8 (list '. (symbol (str "target" i))
            (symbol (str "method" i))
            (symbol (str "arg" i))
            (inc i))
    9 (list 'with-local-vars
            (vector 'x i 'y (inc i))
            (list '+ 'x 'y))))

(emit-case :code-dispatch-generated-corpus
           (mapv (fn [i]
                   (let [kind (mod i 10)
                         margin (case kind
                                  5 24
                                  7 24
                                  8 16
                                  (+ 16 (* 8 (mod i 4))))
                         form (generated-code-form i)]
                     [margin (rendered-code margin form)]))
                 (range 40)))

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

(emit-case :cl-format-ratio-numeric-directives
           (let [formats ["~D" "~10D"
                          "~,2F" "~10,2F"
                          "~,3E" "~12,3E"
                          "~,3G" "~12,3G"
                          "~$" "~10,2$"]
                 values [1/2 -3/2 22/7 1/10]]
             (mapv (fn [fmt]
                     (mapv (fn [value]
                             [fmt value (pprint/cl-format nil fmt value)])
                           values))
                   formats)))

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
