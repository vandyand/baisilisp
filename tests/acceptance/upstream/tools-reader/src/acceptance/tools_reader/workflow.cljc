(ns acceptance.tools-reader.workflow
  (:require [clojure.string :as str]
            [clojure.tools.reader :as tr]
            [clojure.tools.reader.default-data-readers :as ddr]
            [clojure.tools.reader.edn :as edn]
            [clojure.tools.reader.impl.commons :as commons]
            [clojure.tools.reader.impl.errors :as errors]
            [clojure.tools.reader.impl.inspect :as inspect]
            [clojure.tools.reader.impl.utils :as utils]
            [clojure.tools.reader.reader-types :as rt]))

#?(:clj (import [java.io ByteArrayInputStream])
   :lpy (import fractions))

(defn error? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn thrown-summary [f]
  (try
    (f)
    {:thrown? false}
    (catch #?(:clj Throwable :lpy python/Exception) e
      {:thrown? true
       :message (ex-message e)
       :data (select-keys (ex-data e)
                          [:type :ex-kind :file :line :col])})))

(defn sym-data [value]
  (if (symbol? value)
    {:namespace (namespace value)
     :name (name value)}
    value))

(defn normalize-form [form]
  (cond
    (symbol? form) (sym-data form)
    (map? form) (into {}
                      (map (fn [entry]
                             [(normalize-form (key entry))
                              (normalize-form (val entry))]))
                      form)
    (vector? form) (mapv normalize-form form)
    (seq? form) (mapv normalize-form form)
    (set? form) (set (map normalize-form form))
    :else form))

(defn normalize-number [value]
  (cond
    (nil? value) {:kind :nil}
    #?(:clj (instance? clojure.lang.Ratio value)
       :lpy (instance? fractions/Fraction value)) {:kind :ratio
                                                   :value (str value)}
    :else {:kind (cond
                   (integer? value) :integer
                   (float? value) :float
                   :else :number)
           :value (str value)}))

(defn utf8-bytes [s]
  #?(:clj (.getBytes s "UTF-8")
     :lpy (.encode s "utf-8")))

(defn input-bytes [s]
  #?(:clj (ByteArrayInputStream. (utf8-bytes s))
     :lpy (utf8-bytes s)))

(defn instant-ms [value]
  #?(:clj (.getTime value)
     :lpy (inst-ms value)))

(defn timestamp-nanos [value]
  #?(:clj (.getNanos value)
     :lpy (.-nanoseconds value)))

(defn calendar-summary [value]
  #?(:clj {:year (.get value java.util.Calendar/YEAR)
           :month (inc (.get value java.util.Calendar/MONTH))
           :day (.get value java.util.Calendar/DAY_OF_MONTH)
           :hour (.get value java.util.Calendar/HOUR_OF_DAY)
           :minute (.get value java.util.Calendar/MINUTE)
           :second (.get value java.util.Calendar/SECOND)
           :millisecond (.get value java.util.Calendar/MILLISECOND)
           :offset-minutes (quot (+ (.get value java.util.Calendar/ZONE_OFFSET)
                                    (.get value java.util.Calendar/DST_OFFSET))
                                 60000)}
     :lpy {:year (.-year value)
           :month (.-month value)
           :day (.-day value)
           :hour (.-hour value)
           :minute (.-minute value)
           :second (.-second value)
           :millisecond (.-millisecond value)
           :offset-minutes (.-offset-minutes value)}))

(defn public-summary []
  (let [public-names (fn [ns-sym]
                       (sort
                        (remove #(str/starts-with?
                                  %
                                  "clojure.tools.reader.default_data_readers.proxy$")
                                (map name (keys (ns-publics ns-sym))))))]
    {:reader (public-names 'clojure.tools.reader)
     :edn (public-names 'clojure.tools.reader.edn)
     :default-data-readers (public-names
                            'clojure.tools.reader.default-data-readers)
     :reader-types (public-names 'clojure.tools.reader.reader-types)
     :commons (public-names 'clojure.tools.reader.impl.commons)
     :errors (public-names 'clojure.tools.reader.impl.errors)
     :inspect (public-names 'clojure.tools.reader.impl.inspect)
     :utils (public-names 'clojure.tools.reader.impl.utils)}))

(defn read-form [source]
  (normalize-form
   (tr/read-string {:read-cond :allow
                    :features #{#?(:clj :clj :lpy :lpy)}}
                   source)))

(defn core-read-summary []
  (let [r (rt/string-push-back-reader "  [1 :two] ; comment\n {:x 3}")]
    {:read-string-nil (tr/read-string nil)
     :read-string-empty (tr/read-string "")
     :read-string-whitespace-error? (error? #(tr/read-string " \n\t "))
     :read-string-eof (tr/read-string {:eof :done} "")
     :first-only (normalize-form (tr/read-string "alpha beta"))
     :sequential [(normalize-form (tr/read r))
                  (normalize-form (tr/read r))
                  (tr/read r false :done)]
     :read-opts-eof (tr/read {:eof :done}
                             (rt/string-push-back-reader ""))
     :reader-public-vars {:read-delim tr/*read-delim*
                          :default-readers [(contains? tr/default-data-readers 'inst)
                                            (contains? tr/default-data-readers 'uuid)]
                          :map-func [(tr/map-func (range 15))
                                     (tr/map-func (range 16))]}
     :symbol-contracts (let [read-one (fn [source]
                                        (let [reader (rt/string-push-back-reader source)
                                              ch (rt/read-char reader)]
                                          (sym-data (tr/read-symbol reader ch))))
                             indexed (rt/indexing-push-back-reader
                                      "alpha beta"
                                      1
                                      "symbols.cljc")
                             ch (rt/read-char indexed)
                             value (tr/read-symbol indexed ch)]
                         {:specials [(read-one "nil")
                                     (read-one "true")
                                     (read-one "false")
                                     (read-one "/")]
                          :symbols [(read-one "alpha")
                                    (read-one "alpha/beta")
                                    (read-one "foo//")]
                          :stops-at-delimiter (let [reader (rt/string-push-back-reader
                                                            "alpha)")
                                                     ch (rt/read-char reader)]
                                                 [(sym-data (tr/read-symbol reader ch))
                                                  (rt/read-char reader)])
                          :indexed {:value (sym-data value)
                                    :meta (select-keys (meta value)
                                                       [:line :column
                                                        :end-line :end-column
                                                        :file])}
                          :invalid? (error? #(let [reader
                                                   (rt/string-push-back-reader "a/b/c")
                                                   ch (rt/read-char reader)]
                                               (tr/read-symbol reader ch)))})}))

(defn edn-read-summary []
  (let [r (rt/string-push-back-reader "  [1 :two] ; comment\n {:x 3}")]
    {:read-string-nil (edn/read-string nil)
     :read-string-empty (edn/read-string "")
     :read-string-whitespace (edn/read-string " \n\t ")
     :read-string-first-only (normalize-form (edn/read-string "alpha beta"))
     :read-string-data (normalize-form
                        (edn/read-string "{:a [1 2] :b #{:c :d}}"))
     :read-sequential [(normalize-form (edn/read r))
                       (normalize-form (edn/read r))
                       (edn/read r false :done {})]
     :read-opts-eof (edn/read {:eof :done}
                              (rt/string-push-back-reader ""))
     :read-opts-eof-error? (error?
                            #(edn/read {}
                                       (rt/string-push-back-reader "")))
     :clojure-reader-forms-rejected [(error? #(edn/read-string "`a"))
                                     (error? #(edn/read-string "~a"))
                                     (error? #(edn/read-string "@a"))
                                     (error? #(edn/read-string "#'a"))
                                     (error? #(edn/read-string "#()"))
                                     (error? #(edn/read-string "#\"a+\""))
                                     (error? #(edn/read-string "#=(+ 1 2)"))
                                     (error? #(edn/read-string
                                               "#?(:clj :x :lpy :x)"))]}))

(defn tag-summary []
  {:edn-custom (edn/read-string {:readers {'fixture/box
                                           (fn [value] [:box value])}}
                                "#fixture/box [1 2]")
   :edn-default (edn/read-string {:default
                                  (fn [tag value] [:default tag value])}
                                 "#unknown/tag {:x 1}")
   :edn-default-simple-tag (edn/read-string
                            {:default
                             (fn [tag value] [:default tag value])}
                            "#py [1 2]")
   :edn-uuid (str (edn/read-string
                   "#uuid \"550e8400-e29b-41d4-a716-446655440000\""))
   :edn-inst-ms (instant-ms (edn/read-string
                             "#inst \"2020-01-02T03:04:05.000Z\""))
   :reader-dynamic {:data-reader
                    (binding [tr/*data-readers*
                              {'fixture/box (fn [value] [:box value])}]
                      (tr/read-string "#fixture/box [1 2]"))
                    :default-reader
                    (binding [tr/*default-data-reader-fn*
                              (fn [tag value] [:default tag value])]
                      (tr/read-string "#fixture/box [1 2]"))
                    :suppress-read
                    (binding [tr/*suppress-read* true]
                      (let [value (tr/read-string "#fixture/box [1 2]")]
                        [(tagged-literal? value)
                         (.-tag value)
                         (.-form value)]))
                    :read-eval [(tr/read-string "#=(+ 20 22)")
                                (binding [tr/*read-eval* false]
                                  (error? #(tr/read-string "#=(+ 20 22)")))
                                (binding [tr/*read-eval* :unknown]
                                  (error? #(tr/read-string "1")))]}})

(defn read-cond-summary []
  (let [cond-source "#?(:clj :clj :lpy :lpy :default :default)"
        preserve-source "#?(:clj [:clj 1] :lpy [:lpy 2])"
        splicing ["[0 #?@(:clj [1 2] :lpy [1 2]) 3]"
                  "(0 #?@(:clj [1 2] :lpy [1 2]) 3)"
                  "{:a 1 #?@(:clj [:b 2] :lpy [:b 2]) :c 3}"
                  "[#_ :discard #?@(:clj [:kept] :lpy [:kept])]"]]
    {:allow (= #?(:clj :clj :lpy :lpy)
               (tr/read-string {:read-cond :allow
                                :features #{#?(:clj :clj :lpy :lpy)}}
                               cond-source))
     :preserve (let [value (tr/read-string {:read-cond :preserve}
                                           preserve-source)
                     form #?(:clj (.-form value)
                             :lpy (:form value))]
                 [(some? form) form])
     :splicing (mapv read-form splicing)
     :rejected [(error? #(tr/read-string "#?(:clj :x :lpy :x)"))
                (error? #(tr/read-string "#?@(:clj [1] :lpy [1])"))]}))

(defn reader-types-summary []
  (let [stream-reader (rt/input-stream-reader (input-bytes "ab"))
        stream-pbr (rt/input-stream-push-back-reader (input-bytes "cd") 2)
        constructed-stream (rt/->InputStreamReader (input-bytes "xy") nil)
        pushed (rt/push-back-reader (rt/string-reader "ef") 2)
        indexed (rt/indexing-push-back-reader "gh\nij" 2 "expanded.cljc")
        logging (rt/source-logging-push-back-reader "kl" 2 "logged.cljc")
        constructed-indexed (rt/->IndexingPushbackReader
                             (rt/string-reader "mn")
                             5
                             7
                             true
                             \m
                             6
                             "sample.cljc"
                             false)
        constructed-logging (rt/->SourceLoggingPushbackReader
                             (rt/string-reader "op")
                             2
                             3
                             true
                             \o
                             2
                             "source.cljc"
                             []
                             false)]
    {:protocol-vars [(some? rt/Reader)
                     (some? rt/IndexingReader)
                     (some? rt/IPushbackReader)
                     (some? rt/ReaderCoercer)
                     (some? rt/PushbackReaderCoercer)]
     :input [(rt/read-char stream-reader)
             (rt/read-char constructed-stream)
             (rt/read-char stream-pbr)]
     :pushback (let [peeked (rt/peek-char pushed)
                     first-read (rt/read-char pushed)
                     unread-read (do (rt/unread pushed \e)
                                     (rt/read-char pushed))]
                 [peeked first-read unread-read])
     :line (let [starts-first? (rt/line-start? indexed)
                 first-line (rt/read-line indexed)
                 starts-second? (rt/line-start? indexed)
                 second-line (rt/read-line indexed)
                 eof-line (rt/read-line indexed)]
             [starts-first? first-line starts-second? second-line eof-line])
     :constructed {:indexed [(rt/get-line-number constructed-indexed)
                             (rt/get-column-number constructed-indexed)
                             (rt/get-file-name constructed-indexed)
                             (rt/indexing-reader? constructed-indexed)]
                   :logging [(rt/get-file-name constructed-logging)
                             (rt/source-logging-reader? constructed-logging)]}
     :source-log [(rt/log-source* logging (fn [] :logged))
                  (rt/log-source logging :macro-logged)]
     :coercion [(rt/read-char (rt/to-rdr "xy"))
                (rt/read-char (rt/to-pbr (rt/to-rdr "xy") 2))]
     :merged-meta (meta (rt/merge-meta (with-meta 'value {:source :old :a 1})
                                       {:b 2}))}))

(defn commons-summary []
  {:number-literal [(let [r (rt/string-push-back-reader "23")]
                     (commons/number-literal? r \1))
                   (let [r (rt/string-push-back-reader "x")]
                     (commons/number-literal? r \-))
                   (let [r (rt/string-push-back-reader "9")]
                     (commons/number-literal? r \+))
                   (let [r (rt/string-push-back-reader "x")]
                     (commons/number-literal? r \a))]
   :match-number (mapv (fn [source]
                         [source (normalize-number
                                  (commons/match-number source))])
                       ["0" "-0" "+42" "0xff" "077" "2r1010" "36rZ"
                        "3/2" "-10/4" "3.5" "6.02e3" "1.25M"
                        "09" "abc"])
   :parse-symbol (mapv (fn [source] [source (commons/parse-symbol source)])
                       ["" "alpha" "alpha/beta" "/" "alpha/" "/beta"
                        "alpha/beta/gamma" "::kw" "x:" "ns/1"])
   :read-past (let [r (rt/string-push-back-reader "   abc")]
                [(commons/read-past #{\space} r)
                 (rt/read-char r)])
   :skip-line (let [r (rt/string-push-back-reader "abc\ndef")]
                [(identical? r (commons/skip-line r))
                 (rt/read-char r)])
   :comment (let [r (rt/string-push-back-reader "comment\nnext")]
              [(identical? r (commons/read-comment r))
               (rt/read-char r)])
   :throwing-reader (let [summary (thrown-summary
                                   #((commons/throwing-reader "boom")
                                     (rt/string-push-back-reader "x")))]
                      (select-keys summary [:thrown? :message]))})

(defn default-data-readers-summary []
  (let [validating-vector (ddr/validated vector)]
    {:parse (mapv #(ddr/parse-timestamp vector %)
                  ["2024"
                   "2024-02"
                   "2024-02-03"
                   "2024-02-03T04"
                   "2024-02-03T04:05"
                   "2024-02-03T04:05:06.123456789123Z"
                   "2024-02-03T04:05:06.7-07:30"])
     :invalid-parse (mapv #(error? (fn [] (ddr/parse-timestamp vector %)))
                          [nil "" "2024-1" "2024-01-01T" "not an instant"])
     :validated-ok (validating-vector 2024 2 29 23 59 60
                                      123456789 -1 7 30)
     :validated-errors [(error? #(validating-vector 2024 13 1 0 0 0 0 0 0 0))
                        (error? #(validating-vector 2023 2 29 0 0 0 0 0 0 0))
                        (error? #(validating-vector 2024 1 1 24 0 0 0 0 0 0))
                        (error? #(validating-vector 2024 1 1 0 0 0
                                                     1000000000 0 0 0))]
     :date-ms (mapv #(instant-ms (ddr/read-instant-date %))
                    ["2024"
                     "2024-02-03T04:05:06.123456789123Z"
                     "2024-02-03T04:05:06.7-07:30"
                     "2024-01-01T23:59:60.999999999Z"])
     :calendar (mapv #(calendar-summary (ddr/read-instant-calendar %))
                     ["2024"
                      "2024-02-03T04:05:06.123456789123Z"
                      "2024-02-03T04:05:06.7-07:30"
                      "2024-01-01T23:59:60.999999999-02:30"])
     :timestamp (mapv (fn [source]
                        (let [value (ddr/read-instant-timestamp source)]
                          {:inst-ms (instant-ms value)
                           :nanos (timestamp-nanos value)}))
                      ["2024"
                       "2024-02-03T04:05:06.123456789123Z"
                       "2024-02-03T04:05:06.7-07:30"
                       "2024-01-01T23:59:60.999999999Z"])
     :uuid [(str (ddr/default-uuid-reader
                  "550e8400-e29b-41d4-a716-446655440000"))
            (str (ddr/default-uuid-reader
                  "550E8400-E29B-41D4-A716-446655440000"))]
     :invalid [(error? #(ddr/read-instant-date "2024-99"))
               (error? #(ddr/read-instant-date "2023-02-29"))
               (error? #(ddr/read-instant-date "2024-01-01T00:00:60Z"))
               (error? #(ddr/read-instant-date "not an instant"))
               (error? #(ddr/default-uuid-reader "not-a-uuid"))]}))

(defn error-boundary-summary []
  (let [rdr #(rt/indexing-push-back-reader "abc\nxyz" 1 "reader.cljc")]
    {:read-rejections (mapv (fn [source]
                              {:source source
                               :reader-error? (error? #(tr/read-string source))
                               :edn-error? (error? #(edn/read-string source))})
                            ["]"
                             "(1 2"
                             "[1 2"
                             "{:a 1"
                             "{:a}"
                             "#{:a"
                             "foo/bar/baz"
                             "#unknown/tag 1"])
     :direct-errors [(thrown-summary #(errors/reader-error (rdr) "boom"))
                     (thrown-summary #(errors/throw-invalid (rdr) :token "abc"))
                     (thrown-summary #(errors/throw-bad-char (rdr) :string \q))
                     (thrown-summary #(errors/throw-unmatch-delimiter (rdr) \]))
                     (thrown-summary
                      #(errors/throw-invalid-character-literal (rdr) "ZZ"))
                     (thrown-summary
                      #(errors/throw-unknown-reader-tag (rdr) 'demo/tag))]
     :inspect {:scalars [(inspect/inspect nil)
                         (inspect/inspect true)
                         (inspect/inspect false)
                         (inspect/inspect 42)
                         (inspect/inspect 3/2)
                         (inspect/inspect :kw)
                         (inspect/inspect 'sym)]
               :strings [(inspect/inspect "")
                         (inspect/inspect "short")
                         (inspect/inspect "abcdefghijklmnopqrst")
                         (inspect/inspect "abcdefghijklmnopqrstu")
                         (inspect/inspect true "abcdef")]
               :collections [(inspect/inspect [])
                             (inspect/inspect [1 2 3])
                             (inspect/inspect '(1 2 3))
                             (inspect/inspect {:a [1 "abcdef"]})
                             (inspect/inspect #{:a})]}
     :utils {:char [(utils/char nil)
                    (utils/char false)
                    (str (utils/char 65))
                    (str (utils/char \Z))
                    (error? #(utils/char "A"))
                    (error? #(utils/char -1))]
             :predicates {:whitespace [(utils/whitespace? nil)
                                       (utils/whitespace? \space)
                                       (utils/whitespace? \tab)
                                       (utils/whitespace? \,)
                                       (utils/whitespace? \a)]
                          :numeric [(utils/numeric? nil)
                                    (utils/numeric? \0)
                                    (utils/numeric? \7)
                                    (utils/numeric? \a)]
                          :newline [(utils/newline? nil)
                                    (utils/newline? \newline)
                                    (utils/newline? \return)
                                    (utils/newline? \a)]}
             :metadata [(utils/desugar-meta :private)
                        (utils/desugar-meta 'String)
                        (utils/desugar-meta "String")
                        (utils/desugar-meta '[String Long])
                        (utils/desugar-meta {:a 1})
                        (utils/desugar-meta 42)]
             :namespace-keys (vec (utils/namespace-keys
                                   "demo"
                                   ['a :b '_/c :_/d 'x/y :x/y "s" 1]))
             :second' [(utils/second' [])
                       (utils/second' [nil 2])
                       (utils/second' [false 2])
                       (utils/second' [1 2])]
             :ex-info? [(utils/ex-info? (ex-info "x" {:a 1}))
                        (utils/ex-info? #?(:clj (RuntimeException. "x")
                                           :lpy (python/Exception "x")))
                        (utils/ex-info? nil)]}}))

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(def generated-atoms
  ["nil"
   "true"
   "false"
   "0"
   "42"
   "-7"
   "3.5"
   "-0.0"
   "3/2"
   "##Inf"
   "##-Inf"
   "##NaN"
   "alpha"
   "alpha/beta"
   "/"
   ":kw"
   ":ns/kw"
   "\"line\\nquote\\\"slash\\\\\""
   "\\newline"])

(defn seeded-form [seed depth]
  (let [s1 (next-seed seed)
        s2 (next-seed s1)
        s3 (next-seed s2)]
    (if (zero? depth)
      [(nth generated-atoms (mod seed (count generated-atoms))) s1]
      (case (mod seed 7)
        0 [(nth generated-atoms (mod seed (count generated-atoms))) s1]
        1 (let [[a n1] (seeded-form s1 (dec depth))
                [b n2] (seeded-form n1 (dec depth))]
            [(str "[" a " " b "]") n2])
        2 (let [[a n1] (seeded-form s1 (dec depth))
                [b n2] (seeded-form n1 (dec depth))]
            [(str "(" a " " b ")") n2])
        3 (let [[a n1] (seeded-form s1 (dec depth))]
            [(str "{:k" (mod s1 17) " " a "}") n1])
        4 (let [[a n1] (seeded-form s1 (dec depth))]
            [(str "#{" a "}") n1])
        5 ["^:private alpha" s1]
        6 (let [[a _] (seeded-form s2 (dec depth))]
            [(str "#_ " a " " (nth generated-atoms
                                    (mod s3 (count generated-atoms)))) s3])))))

(defn generated-case [seed]
  (let [[source next] (seeded-form seed 3)
        value (read-form source)
        read-plus (tr/read+string {:read-cond :allow
                                   :features #{#?(:clj :clj :lpy :lpy)}}
                                  (rt/source-logging-push-back-reader source))]
    {:seed seed
     :source source
     :value value
     :source-length (count (second read-plus))
     :roundtrip-source? (= source (second read-plus))
     :next-seed next}))

(defn generated-summary []
  {:forms (loop [remaining 96
                 seed 439041101
                 result []]
            (if (zero? remaining)
              result
              (let [case (generated-case seed)]
                (recur (dec remaining)
                       (:next-seed case)
                       (conj result (dissoc case :next-seed))))))
   :adversarial (mapv (fn [source]
                        {:source source
                         :reader-error? (error? #(tr/read-string source))
                         :edn-error? (error? #(edn/read-string source))})
                      ["]"
                       "(1 2"
                       "[1 2"
                       "{:a 1"
                       "{:a}"
                       "#{:a"
                       "foo/bar/baz"
                       "::kw"
                       "`a"
                       "~a"
                       "@a"
                       "#'a"
                       "#()"
                       "#\"a+\""
                       "#=(+ 1 2)"
                       "#?(:clj :x :lpy :x)"
                       "#?@(:clj [1] :lpy [1])"
                       "#unknown/tag 1"])})
