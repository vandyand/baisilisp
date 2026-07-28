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

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy Exception) _ true)))

(defn with-pretty-writer-output [f]
  (normalize-newlines
   (with-out-str
     (let [writer (pprint/get-pretty-writer *out*)]
       (binding [*out* writer
                 pprint/*print-pretty* true]
         (f)
         (.flush writer))))))

(defn rendered-code [margin form]
  (binding [pprint/*print-right-margin* margin]
    (rendered #(pprint/with-pprint-dispatch pprint/code-dispatch
                 (pprint/pprint form)))))

(defn rendered-write [form & opts]
  (normalize-newlines
   (with-out-str
     (apply pprint/write form opts))))

(defn direct-fresh-line-output []
  (-> (with-out-str
        (pprint/fresh-line)
        (print "a")
        (pprint/fresh-line)
        (pprint/fresh-line)
        (print "b"))
      (str/replace "\r\n" "\n")))

(defn pretty-writer-fresh-line-output []
  (with-pretty-writer-output
   #(do
      (.write *out* "a")
      (pprint/fresh-line)
      (.write *out* "b"))))

(defn indent-helper-output []
  (with-pretty-writer-output
   #(pprint/pprint-logical-block :prefix "[" :suffix "]"
      (pprint/write-out :alpha)
      (.write *out* " ")
      (pprint/pprint-indent :block 2)
      (pprint/pprint-newline :linear)
      (pprint/write-out :beta))))

(defn print-length-loop-output []
  (binding [*print-length* 2]
    (with-pretty-writer-output
     #(pprint/pprint-logical-block :prefix "[" :suffix "]"
        (pprint/print-length-loop [xs (seq [1 2 3])]
          (when xs
            (pprint/write-out (first xs))
            (when (next xs)
              (.write *out* " ")
              (recur (next xs)))))))))

(defn set-dispatch-result []
  (let [old @#'pprint/*print-pprint-dispatch*]
    (try
      (pprint/set-pprint-dispatch pprint/simple-dispatch)
      (ifn? @#'pprint/*print-pprint-dispatch*)
      (finally
        (pprint/set-pprint-dispatch old)))))

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

(emit-case :dynamic-vars-and-writer-helpers
           {:dynamic-vars {:base (binding [pprint/*print-base* 16]
                                   pprint/*print-base*)
                           :radix (binding [pprint/*print-radix* true]
                                    pprint/*print-radix*)
                           :miser (binding [pprint/*print-miser-width* 4]
                                    pprint/*print-miser-width*)
                           :pretty (binding [pprint/*print-pretty* true]
                                     pprint/*print-pretty*)
                           :dispatch (ifn? pprint/*print-pprint-dispatch*)
                           :suppress (binding [pprint/*print-suppress-namespaces* true]
                                       pprint/*print-suppress-namespaces*)}
            :helpers {:fresh (direct-fresh-line-output)
                      :pretty-writer (pretty-writer-fresh-line-output)
                      :tab-rejected (rejected? #(pprint/pprint-tab :line 5 1))
                      :indent (indent-helper-output)
                      :length-loop (print-length-loop-output)
                      :pp (rendered #(pprint/pp))
                      :set-dispatch (set-dispatch-result)}})

#?(:lpy
   (emit-case :basilisp-extension-writer-protocol-boundary
              (let [block (pprint/LogicalBlock nil "[" nil "]" 0 0 false false)]
                {:internal-dynamic-vars [(binding [pprint/*current-level* 7]
                                           pprint/*current-level*)
                                         (binding [pprint/*current-length* 3]
                                           pprint/*current-length*)
                                         (binding [pprint/*print-sort-keys* true]
                                           pprint/*print-sort-keys*)]
                 :token-constructors [(some? block)
                                      (some? (pprint/StartBlock block 0 1))
                                      (some? (pprint/EndBlock block 1 2))
                                      (some? (pprint/Blob "x" 0 1))
                                      (some? (pprint/Indent block :block 2 1 1))
                                      (some? (pprint/Newline block :mandatory 1 1))]
                 :pretty-writer-var (some? pprint/PrettyWriter)
                 :direct-protocol-output (normalize-newlines
                                          (with-out-str
                                            (let [writer (pprint/get-pretty-writer *out* 12)]
                                              (binding [*out* writer
                                                        pprint/*print-pretty* true]
                                                (pprint/start-block writer "[" nil "]")
                                                (.write writer "alpha")
                                                (pprint/pp-indent writer :block 2)
                                                (pprint/pp-newline writer :mandatory)
                                                (.write writer "beta")
                                                (pprint/end-block writer)
                                                (.flush writer)))))}))
   :clj
   (emit-case :basilisp-extension-writer-protocol-boundary
              {:internal-dynamic-vars [7 3 true]
               :token-constructors [true true true true true true]
               :pretty-writer-var true
               :direct-protocol-output "[alpha\n   beta]"}))

(emit-case :write-contracts
           {:base (with-out-str
                    (pprint/write [31 32] :base 16 :radix true))
            :suppress (with-out-str
                        (pprint/write 'foo/bar :suppress-namespaces true))
            :default (with-out-str
                       (pprint/write [1 2 [3 4]]))
            :pretty (normalize-newlines
                     (with-out-str
                       (pprint/write [1 2 [3 4]]
                                     :pretty true
                                     :right-margin 8)))})

(emit-case :write-option-adversarial
           {:pretty-false-margin (rendered-write [1 2 [3 4]]
                                                 :pretty false
                                                 :right-margin 4)
            :length-level (rendered-write (sorted-map :a [1 2 3 4]
                                                      :b (sorted-map :c [5 6]))
                                          :pretty true
                                          :right-margin 12
                                          :length 1
                                          :level 3)
            :length-zero-map (rendered-write (sorted-map :a 1 :b 2)
                                             :pretty true
                                             :length 0)
            :level-zero (rendered-write [1 [2 [3]]]
                                        :pretty true
                                        :level 0)
            :base-radix-ratio (rendered-write [31 -31 3/2]
                                              :base 16
                                              :radix true)
            :suppress-nested-namespaces (rendered-write ['foo/bar
                                                         {:k 'alpha/beta}
                                                         [:ns/name]]
                                                        :pretty true
                                                        :suppress-namespaces true)
            :meta-on (rendered-write (with-meta [1 2] {:tag 'demo/tag})
                                     :pretty true
                                     :meta true)
            :meta-off (binding [*print-meta* true]
                        (rendered-write (with-meta [1 2] {:tag 'demo/tag})
                                        :pretty true
                                        :meta false))})

(emit-case :nested-data-margin-corpus
           (let [forms [(sorted-map :alpha [1 2 3]
                                    :beta (sorted-map :gamma [4 5]))
                        ['alpha (sorted-map :beta [1 2]) ['gamma ['delta]]]
                        [[1 2] [3 [4 5]] (sorted-map :six 6)]
                        (list 'let ['x 1 'y '(+ x 2)] '(+ x y))]
                 margins [8 12 20 40]]
             (mapv (fn [form]
                     (mapv (fn [margin]
                             [margin
                              (binding [pprint/*print-right-margin* margin]
                                (rendered #(pprint/pprint form)))])
                           margins))
                   forms)))

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

(def exact-width-code-cases
  [[12 :condp-do
    '(condp = command
       :start (do (prepare! system) (start! system))
       :stop (do (stop! system) :stopped)
       :restart (do (stop! system) (start! system))
       :unknown)]
   [16 :condp-do
    '(condp = command
       :start (do (prepare! system) (start! system))
       :stop (do (stop! system) :stopped)
       :restart (do (stop! system) (start! system))
       :unknown)]
   [22 :condp-vector-test
    '(condp some? (lookup env key)
       nil :missing
       false :disabled
       (vector :a :b) (handle-vector env key)
       :default)]
   [18 :if-not-body
    '(if-not (ready? (state system))
       (do
         (prepare! system)
         (start! system)
         (await-ready system))
       (report-ready system))]
   [20 :when-not-body
    '(when-not (ready? (state system))
       (prepare! system)
       (start! system)
       (await-ready system))]
   [22 :locking-body
    '(locking lock
       (swap! state assoc :phase :running)
       (snapshot state)
       (notify! watchers))]
   [24 :nested-body
    '(when-not (ready? system)
       (condp = command
         :start (start! system)
         :stop (stop! system)
         :unknown)
       (if-not (healthy? system)
         (restart! system)
         (report-ready system)))]])

(emit-case :code-dispatch-exact-width-adversarial
           (mapv (fn [[margin kind form]]
                   [margin kind (rendered-code margin form)])
                 exact-width-code-cases))

(emit-case :print-table
           {:inferred (rendered #(pprint/print-table [(sorted-map :a 1 :b "two")
                                                      (sorted-map :a 300 :b "four")]))
            :explicit (rendered #(pprint/print-table [:b :a]
                                                     [{:a 1 :b "two"}
                                                      {:a 300 :b "four"}]))
            :empty (rendered #(pprint/print-table [:a :b] []))})

(emit-case :print-table-adversarial
           {:missing-and-nil-cells
            (rendered #(pprint/print-table [:a :b :c]
                                           [(sorted-map :a 1 :b nil)
                                            (sorted-map :a 222 :c "see")
                                            (sorted-map :b "bee" :c nil)]))
            :inferred-keys-ignore-later-only-columns
            (rendered #(pprint/print-table [(sorted-map :alpha "x" :beta 22)
                                            (sorted-map :alpha "longer" :gamma nil)]))
            :mixed-width-values
            (rendered #(pprint/print-table [:k :v]
                                           [(sorted-map :k :short :v 1)
                                            (sorted-map :k :much-longer-key
                                                        :v "wide text")
                                            (sorted-map :k nil :v :keyword)]))})

(emit-case :cl-format-core
           {:numbers [(pprint/cl-format nil "~D ~:D ~@D" 12 1234567 12)
                      (pprint/cl-format nil "~,2F" 12.5)
                      (pprint/cl-format nil "~4,'0X" 31)]
            :iteration (pprint/cl-format nil "~{~A~^, ~}" [:a :b :c])
            :conditional (pprint/cl-format nil "~[zero~;one~;two~:;many~]" 3)
            :plural (pprint/cl-format nil "~D file~:P copied" 2)
            :fresh-line (normalize-newlines (pprint/cl-format nil "a~&b~%c"))})

(emit-case :cl-format-control-flow-adversarial
           {:nested-iteration (pprint/cl-format nil "~{(~{~A~^,~})~^;~}"
                                                [[1 2] [:a :b :c]])
            :case-conversion (pprint/cl-format nil
                                               "~:@(~A~) ~:(~A~) ~@(~A~) ~(~A~)"
                                               "hello world"
                                               "hello world"
                                               "hello world"
                                               "HELLO")
            :argument-jumps (pprint/cl-format nil "~A ~:*~A ~2:*~A ~A"
                                              :a :b :c)
            :escape-in-iteration (pprint/cl-format nil "~{~A~^|~}" [:a :b :c])
            :remaining-conditional (pprint/cl-format nil
                                                     "~#[none~;one=~A~;two=~A/~A~:;many~]"
                                                     :x :y :z)
            :out-of-range-conditional (pprint/cl-format nil
                                                       "~[zero~;one~;two~]"
                                                       5)
            :plural-boundaries (pprint/cl-format nil "~:P|~P|~@P|~:@P"
                                                 1 2 1 2)})

(emit-case :cl-format-english-roman-boundaries
           (mapv (fn [n]
                   [n (pprint/cl-format nil "~R|~:R|~@R|~:@R" n n n n)])
                 [4 9 19 44 99 944]))

(emit-case :cl-format-error-boundaries
           {:non-consuming-iteration (rejected?
                                      #(pprint/cl-format nil
                                                         "~{~#[Z~;O=~A~;T=~A/~A~:;M~]~^;~}"
                                                         [[:a] [:b :c] [:d :e :f]]))
             :missing-argument (rejected? #(pprint/cl-format nil "~A ~A" :only-one))
            :bad-directive (rejected? #(pprint/cl-format nil "~Q" :x))
            :standalone-conditional-newline (rejected?
                                             #(pprint/cl-format nil "a~_b"))})

(emit-case :cl-format-directive-adversarial
           {:radix [(pprint/cl-format nil "~B|~O|~D|~X"
                                      10 10 10 10)
                    (pprint/cl-format nil "~:B|~:O|~:D|~:X"
                                      1234567 1234567 1234567 1234567)
                    (pprint/cl-format nil "~@B|~@O|~@D|~@X"
                                      10 10 10 10)]
            :characters (pprint/cl-format nil "~C|~:C|~@C|~:@C"
                                          \A \space \newline \tab)
            :strings (pprint/cl-format nil "~A|~S|~10A|~10S|~10@A|~10@S"
                                       "x y" "x y" "x" "x" "x" "x")
            :justification (pprint/cl-format nil "~10<~A~>|~10:@<~A~>"
                                             "abc" "abc")
            :indirection [(pprint/cl-format nil "~?" "~A/~A" [:x :y])
                          (pprint/cl-format nil "~@?" "~A/~A" :x :y)]
            :tabulation [(pprint/cl-format nil
                                           "a~5Tz|a~5,2Tz|a~5@Tz|a~5,2@Tz")
                         (pprint/cl-format nil
                                           "~5@Tz|ab~5,2@Tz|abc~5,2@Tz|abcd~5,2@Tz")]
            :fresh-line (mapv #(normalize-newlines (pprint/cl-format nil %))
                               ["~&a"
                                "a~&b"
                                "a~%~&b"
                                "a~2&b"])})

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
