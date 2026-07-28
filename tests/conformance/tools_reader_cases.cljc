;; Portable clojure.tools.reader/basilisp.tools.reader public surface and
;; reader-types constructor/coercer behavior.

(require '[clojure.tools.reader :as tr]
         '[clojure.tools.reader.default-data-readers :as ddr]
         '[clojure.tools.reader.edn :as edn]
         '[clojure.tools.reader.impl.commons :as commons]
         '[clojure.tools.reader.impl.errors :as errors]
         '[clojure.tools.reader.impl.inspect :as inspect]
         '[clojure.tools.reader.impl.utils :as utils]
         '[clojure.tools.reader.reader-types :as rt])

#?(:clj (import [java.io ByteArrayInputStream]))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy Exception) _ true)))

(defn thrown-summary [f]
  (try
    (f)
    {:thrown? false}
    (catch #?(:clj Throwable :lpy Exception) e
      {:thrown? true
       :message (ex-message e)
       :data (select-keys (ex-data e)
                          [:type :ex-kind :file :line :col])})))

(defn sym-data [value]
  (if (symbol? value)
    {:name (name value)
     :namespace (namespace value)}
    value))

(defn read-summary [source]
  {:source source
   :value (tr/read-string {:read-cond :allow
                           :features #{#?(:clj :clj :lpy :lpy)}}
                          source)})

(defn normalize-symbol [value]
  (if (symbol? value)
    {:name (name value)
     :namespace (namespace value)}
    value))

(defn normalize-form [form]
  (cond
    (symbol? form) (normalize-symbol form)
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
  (if (nil? value)
    {:kind :nil}
    {:value (str value)}))

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

(defn next-seed [seed]
  (mod (+ (* seed 1103515245) 12345) 2147483648))

(defn pad2 [n]
  (let [s (str n)]
    (if (= 1 (count s)) (str "0" s) s)))

(defn seeded-instant-source [seed]
  (let [s1 (next-seed seed)
        s2 (next-seed s1)
        s3 (next-seed s2)
        s4 (next-seed s3)
        s5 (next-seed s4)
        s6 (next-seed s5)
        year (+ 1970 (mod s1 80))
        month (inc (mod s2 12))
        day (inc (mod s3 28))
        hour (mod s4 24)
        minute (mod s5 60)
        second (mod s6 60)
        nanos (mod (* s6 1664525) 1000000000)
        offset-hour (mod s5 14)
        offset-minute (mod s4 60)
        sign (if (zero? (mod s3 2)) "+" "-")]
    (str year "-" (pad2 month) "-" (pad2 day) "T"
         (pad2 hour) ":" (pad2 minute) ":" (pad2 second) "."
         nanos sign (pad2 offset-hour) ":" (pad2 offset-minute))))

(emit-case :reader-public-surface
           (every? #(contains? (ns-publics #?(:clj 'clojure.tools.reader
                                              :lpy 'basilisp.tools.reader))
                               %)
                   '[*alias-map*
                     *data-readers*
                     *default-data-reader-fn*
                     *read-delim*
                     *read-eval*
                     *suppress-read*
                     default-data-readers
                     map-func
                     read
                     read+string
                     read-regex
                     read-string
                     read-symbol
                     resolve-symbol
                     syntax-quote]))

(emit-case :reader-types-public-surface
           (every? #(contains? (ns-publics #?(:clj 'clojure.tools.reader.reader-types
                                              :lpy 'basilisp.tools.reader.reader-types))
                               %)
                   '[->IndexingPushbackReader
                     ->InputStreamReader
                     ->PushbackReader
                     ->SourceLoggingPushbackReader
                     ->StringReader
                     IPushbackReader
                     IndexingReader
                     PushbackReaderCoercer
                     Reader
                     ReaderCoercer
                     get-column-number
                     get-file-name
                     get-line-number
                     indexing-push-back-reader
                     indexing-reader?
                     input-stream-push-back-reader
                     input-stream-reader
                     line-start?
                     log-source
                     log-source*
                     merge-meta
                     peek-char
                     push-back-reader
                     read-char
                     read-line
                     source-logging-push-back-reader
                     source-logging-reader?
                     string-push-back-reader
                     string-reader
                     to-pbr
                     to-rdr
                     unread]))

(emit-case :edn-public-surface
           (every? #(contains? (ns-publics #?(:clj 'clojure.tools.reader.edn
                                              :lpy 'basilisp.tools.reader.edn))
                               %)
                   '[read
                     read-string]))

(emit-case :default-data-readers-public-surface
           (every? #(contains? (ns-publics
                                #?(:clj 'clojure.tools.reader.default-data-readers
                                   :lpy 'basilisp.tools.reader.default-data-readers))
                               %)
                   '[default-uuid-reader
                     parse-timestamp
                     read-instant-calendar
                     read-instant-date
                     read-instant-timestamp
                     validated]))

(emit-case :impl-commons-public-surface
           (every? #(contains? (ns-publics
                                #?(:clj 'clojure.tools.reader.impl.commons
                                   :lpy 'basilisp.tools.reader.impl.commons))
                               %)
                   '[float-pattern
                     int-pattern
                     match-number
                     number-literal?
                     parse-symbol
                     ratio-pattern
                     read-comment
                     read-past
                     skip-line
                     throwing-reader]))

(emit-case :impl-errors-public-surface
           (every? #(contains? (ns-publics
                                #?(:clj 'clojure.tools.reader.impl.errors
                                   :lpy 'basilisp.tools.reader.impl.errors))
                               %)
                   '[eof-error
                     illegal-arg-error
                     reader-error
                     throw-bad-char
                     throw-bad-escape-char
                     throw-bad-metadata
                     throw-bad-metadata-target
                     throw-bad-ns
                     throw-bad-octal-number
                     throw-bad-reader-tag
                     throw-eof-at-dispatch
                     throw-eof-at-start
                     throw-eof-delimited
                     throw-eof-error
                     throw-eof-in-character
                     throw-eof-reading
                     throw-feature-not-keyword
                     throw-invalid
                     throw-invalid-character-literal
                     throw-invalid-number
                     throw-invalid-octal-len
                     throw-invalid-unicode-char
                     throw-invalid-unicode-digit
                     throw-invalid-unicode-digit-in-token
                     throw-invalid-unicode-escape
                     throw-invalid-unicode-len
                     throw-invalid-unicode-literal
                     throw-ns-map-no-map
                     throw-odd-map
                     throw-single-colon
                     throw-unknown-reader-tag
                     throw-unmatch-delimiter
                     throw-unsupported-character]))

(emit-case :impl-inspect-public-surface
           (every? #(contains? (ns-publics
                                #?(:clj 'clojure.tools.reader.impl.inspect
                                   :lpy 'basilisp.tools.reader.impl.inspect))
                               %)
                   '[inspect
                     inspect*]))

(emit-case :impl-utils-public-surface
           (every? #(contains? (ns-publics
                                #?(:clj 'clojure.tools.reader.impl.utils
                                   :lpy 'basilisp.tools.reader.impl.utils))
                               %)
                   '[<=clojure-1-7-alpha5
                     char
                     compile-when
                     desugar-meta
                     ex-info?
                     make-var
                     namespace-keys
                     newline?
                     numeric?
                     second'
                     whitespace?]))

(emit-case :map-func
           [(tr/map-func (range 15))
            (tr/map-func (range 16))])

(emit-case :reader-public-vars-direct
           (let [quoted (tr/syntax-quote (map inc [1 2]))]
             {:read-delim tr/*read-delim*
              :default-data-readers [(contains? tr/default-data-readers 'inst)
                                     (contains? tr/default-data-readers 'uuid)]
              :syntax-quote-shape [(seq? quoted)
                                   (count quoted)
                                   (mapv #(if (symbol? %)
                                            (name %)
                                            (pr-str %))
                                         quoted)]}))

(emit-case :read-symbol-contracts
           (let [read-one (fn [source]
                            (let [r  (rt/string-push-back-reader source)
                                  ch (rt/read-char r)]
                              (sym-data (tr/read-symbol r ch))))
                 indexed  (rt/indexing-push-back-reader "alpha beta" 1 "symbols.cljc")
                 ich      (rt/read-char indexed)
                 value    (tr/read-symbol indexed ich)]
             {:specials [(read-one "nil")
                         (read-one "true")
                         (read-one "false")
                         (read-one "/")]
              :symbols [(read-one "alpha")
                        (read-one "alpha/beta")
                        (read-one "foo//")]
              :stops-at-delimiter (let [r  (rt/string-push-back-reader "alpha)")
                                         ch (rt/read-char r)]
                                     [(sym-data (tr/read-symbol r ch))
                                      (rt/read-char r)])
              :indexed {:value (sym-data value)
                        :meta (select-keys (meta value)
                                           [:line :column :end-line :end-column :file])}
              :invalid? (rejected? #(let [r (rt/string-push-back-reader "a/b/c")
                                           ch (rt/read-char r)]
                                       (tr/read-symbol r ch)))}))

(emit-case :read-and-read-string-contracts
           (let [r (rt/string-push-back-reader "  [1 :two] ; comment\n {:x 3}")]
             {:read-string-nil (tr/read-string nil)
              :read-string-empty (tr/read-string "")
              :read-string-whitespace-rejected? (rejected? #(tr/read-string " \n\t "))
              :read-string-eof (tr/read-string {:eof :done} "")
              :read-string-first-only (tr/read-string "1 2")
              :read-sequential [(tr/read r)
                                (tr/read r)
                                (tr/read r false :done)]
              :read-opts-eof (tr/read {:eof :done}
                                      (rt/string-push-back-reader ""))
              :unmatched-rejected? (rejected? #(tr/read-string "]"))}))

(emit-case :edn-read-and-read-string-contracts
           (let [r (rt/string-push-back-reader "  [1 :two] ; comment\n {:x 3}")]
             {:read-string-nil (edn/read-string nil)
              :read-string-empty (edn/read-string "")
              :read-string-whitespace (edn/read-string " \n\t ")
              :read-string-first-only (edn/read-string "1 2")
              :read-string-data (normalize-form
                                 (edn/read-string "{:a [1 2] :b #{:c :d}}"))
              :read-sequential [(edn/read r)
                                (edn/read r)
                                (edn/read r false :done {})]
              :read-opts-eof (edn/read {:eof :done}
                                       (rt/string-push-back-reader ""))
              :read-opts-eof-error? (rejected?
                                     #(edn/read {}
                                                (rt/string-push-back-reader "")))
              :unmatched-rejected? (rejected? #(edn/read-string "]"))}))

(emit-case :edn-tagged-reader-contracts
           {:custom (edn/read-string {:readers {'fixture/box
                                                (fn [value] [:box value])}}
                                     "#fixture/box [1 2]")
            :default (edn/read-string {:default
                                       (fn [tag value] [:default tag value])}
                                      "#unknown/tag {:x 1}")
            :default-simple-tag (edn/read-string
                                 {:default
                                  (fn [tag value] [:default tag value])}
                                 "#py [1 2]")
            :uuid (str (edn/read-string
                        "#uuid \"550e8400-e29b-41d4-a716-446655440000\""))
            :inst-some? (some? (edn/read-string
                                "#inst \"2020-01-02T03:04:05.000Z\""))})

(emit-case :default-data-readers-timestamp-contracts
           (let [validating-vector (ddr/validated vector)]
             {:parse (mapv #(ddr/parse-timestamp vector %)
                           ["2024"
                            "2024-02"
                            "2024-02-03"
                            "2024-02-03T04"
                            "2024-02-03T04:05"
                            "2024-02-03T04:05:06.123456789123Z"
                            "2024-02-03T04:05:06.7-07:30"
                            "2024-99"])
              :malformed (mapv #(rejected? (fn [] (ddr/parse-timestamp vector %)))
                                [nil
                                 ""
                                 "2024-1"
                                 "2024-01-01T"
                                 "2024-01-01T00:"
                                 "not an instant"])
              :validated-ok (validating-vector 2024 2 29 23 59 60
                                               123456789 -1 7 30)
              :validated-errors [(rejected? #(validating-vector 2024 13 1
                                                                 0 0 0 0 0 0 0))
                                 (rejected? #(validating-vector 2023 2 29
                                                                 0 0 0 0 0 0 0))
                                 (rejected? #(validating-vector 2024 1 1
                                                                 24 0 0 0 0 0 0))
                                 (rejected? #(validating-vector 2024 1 1
                                                                 0 0 0 1000000000
                                                                 0 0 0))]}))

(emit-case :default-data-readers-instant-contracts
           {:date-ms (mapv #(instant-ms (ddr/read-instant-date %))
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
            :invalid (mapv #(rejected? (fn [] (ddr/read-instant-date %)))
                           ["2024-99"
                            "2023-02-29"
                            "2024-01-01T00:00:60Z"
                            "2010-01-01T24:00:00.000Z"
                            "not an instant"])})

(emit-case :default-data-readers-uuid-and-reader-integration
           {:uuid [(str (ddr/default-uuid-reader
                         "550e8400-e29b-41d4-a716-446655440000"))
                   (str (ddr/default-uuid-reader
                         "550E8400-E29B-41D4-A716-446655440000"))]
            :uuid-invalid [(rejected? #(ddr/default-uuid-reader nil))
                           (rejected? #(ddr/default-uuid-reader 1))
                           (rejected? #(ddr/default-uuid-reader "not-a-uuid"))]
            :reader [(let [value (binding [tr/*data-readers*
                                            {'inst ddr/read-instant-timestamp}]
                                  (tr/read-string
                                   "#inst \"2024-02-03T04:05:06.123456789Z\""))]
                       {:inst-ms (instant-ms value)
                        :nanos (timestamp-nanos value)})
                     (str (binding [tr/*data-readers*
                                    {'uuid ddr/default-uuid-reader}]
                            (tr/read-string
                             "#uuid \"550e8400-e29b-41d4-a716-446655440000\"")))]})

(emit-case :default-data-readers-seeded-instant-corpus
           (loop [remaining 32
                  seed 271828
                  result []]
             (if (zero? remaining)
               result
               (let [source (seeded-instant-source seed)
                     timestamp (ddr/read-instant-timestamp source)]
                 (recur (dec remaining)
                        (next-seed seed)
                        (conj result
                              {:source source
                               :parse (ddr/parse-timestamp vector source)
                               :date-ms (instant-ms (ddr/read-instant-date source))
                               :timestamp-ms (instant-ms timestamp)
                               :nanos (timestamp-nanos timestamp)}))))))

(emit-case :impl-commons-patterns-and-match-number
           {:patterns (mapv (fn [source]
                              {:source source
                               :int? (boolean (re-matches commons/int-pattern source))
                               :ratio? (boolean (re-matches commons/ratio-pattern source))
                               :float? (boolean (re-matches commons/float-pattern source))})
                            ["0"
                             "0N"
                             "42"
                             "-42"
                             "+42"
                             "0x10"
                             "010"
                             "2r101"
                             "36rZ"
                             "3/6"
                             "-10/4"
                             "1.5"
                             "1.5M"
                             "1e3"
                             "1e3M"
                             "09"
                             "2r2"
                             "not-number"])
            :matched (mapv (fn [source]
                              {:source source
                               :value (normalize-number
                                       (commons/match-number source))})
                            ["0"
                             "0N"
                             "42"
                             "-42"
                             "+42"
                             "0x10"
                             "010"
                             "2r101"
                             "36rZ"
                             "3/6"
                             "-10/4"
                             "1.5"
                             "1.5M"
                             "1e3"
                             "1e3M"
                             "09"
                             "not-number"])
            :rejected (mapv #(rejected? (fn [] (commons/match-number %)))
                            ["1/0"
                             "2r2"
                             "37r10"])})

(emit-case :impl-commons-parse-symbol-contracts
           (mapv (fn [source]
                   {:source source
                    :value (commons/parse-symbol source)})
                 [""
                  "alpha"
                  "alpha/beta"
                  "/"
                  "foo//"
                  "foo/bar/baz"
                  "foo/"
                  "/bar"
                  "1abc"
                  "alpha/1"
                  "alpha/:"
                  "alpha:/beta"
                  "alpha:"
                  "::kw"
                  "kw:"
                  "with.dot/name"
                  "with-dash/name?"]))

(emit-case :impl-commons-reader-boundaries
           {:number-literal? [(commons/number-literal?
                              (rt/string-push-back-reader "") \1)
                             (commons/number-literal?
                              (rt/string-push-back-reader "1") \+)
                             (commons/number-literal?
                              (rt/string-push-back-reader "1") \-)
                             (commons/number-literal?
                              (rt/string-push-back-reader "a") \+)
                             (commons/number-literal?
                              (rt/string-push-back-reader "") \+)]
            :read-past (let [r (rt/string-push-back-reader "   abc")]
                         [(commons/read-past #(= % \space) r)
                          (rt/read-char r)])
            :skip-line (let [r (rt/string-push-back-reader "abc\nZ")]
                         [(identical? r (commons/skip-line r))
                          (rt/read-char r)])
            :skip-line-eof (let [r (rt/string-push-back-reader "abc")]
                             [(identical? r (commons/skip-line r))
                              (rt/read-char r)])
            :read-comment (let [r (rt/string-push-back-reader "comment\nZ")]
                            [(identical? r (commons/read-comment r))
                             (rt/read-char r)])
            :throwing-reader (rejected?
                              #((commons/throwing-reader "boom")
                                (rt/string-push-back-reader "")))})

(emit-case :impl-errors-generic-contracts
           {:unindexed [(thrown-summary
                         #(errors/reader-error
                           (rt/string-push-back-reader "abc")
                           "x"
                           "y"))
                        (thrown-summary
                         #(errors/eof-error
                           (rt/string-push-back-reader "abc")
                           "done"))
                        (thrown-summary
                         #(errors/illegal-arg-error
                           (rt/string-push-back-reader "abc")
                           "bad"))]
            :indexed [(thrown-summary
                       #(errors/reader-error
                         (rt/indexing-push-back-reader "abc" 1 "sample.cljc")
                         "xy"))
                      (thrown-summary
                       #(errors/eof-error
                         (rt/indexing-push-back-reader "abc" 1 "sample.cljc")
                         "done"))
                      (thrown-summary
                       #(errors/illegal-arg-error
                         (rt/indexing-push-back-reader "abc" 1 "sample.cljc")
                         "bad"))]})

(emit-case :impl-errors-helper-contracts
           (let [rdr #(rt/indexing-push-back-reader "abc" 1 "sample.cljc")]
             {:eof [(thrown-summary
                     #(errors/throw-eof-delimited (rdr) :list 2 3))
                    (thrown-summary
                     #(errors/throw-eof-delimited (rdr) :vector 2 3 4))
                    (thrown-summary
                     #(errors/throw-eof-at-start (rdr) :map))
                    (thrown-summary
                     #(errors/throw-eof-at-dispatch (rdr)))
                    (thrown-summary
                     #(errors/throw-eof-reading (rdr) :string \a \b))
                    (thrown-summary
                     #(errors/throw-eof-reading (rdr) :regex \a))
                    (thrown-summary
                     #(errors/throw-eof-in-character (rdr)))
                    (thrown-summary
                     #(errors/throw-eof-error (rdr) 7))
                    (thrown-summary
                     #(errors/throw-eof-error (rdr) nil))]
              :reader [(thrown-summary
                        #(errors/throw-odd-map (rdr) 5 6 [:a 1 :b]))
                       (thrown-summary
                        #(errors/throw-invalid-number (rdr) "09"))
                       (thrown-summary
                        #(errors/throw-invalid-unicode-escape (rdr) \x))
                       (thrown-summary
                        #(errors/throw-invalid (rdr) :token "abc"))
                       (thrown-summary
                        #(errors/throw-bad-char (rdr) :string \q))
                       (thrown-summary
                        #(errors/throw-unmatch-delimiter (rdr) \]))
                       (thrown-summary
                        #(errors/throw-invalid-character-literal (rdr) "ZZ"))
                       (thrown-summary
                        #(errors/throw-invalid-octal-len (rdr) "1234"))
                       (thrown-summary
                        #(errors/throw-bad-octal-number (rdr)))
                       (thrown-summary
                        #(errors/throw-unsupported-character (rdr) "newline"))
                       (thrown-summary
                        #(errors/throw-bad-escape-char (rdr) \z))
                       (thrown-summary
                        #(errors/throw-single-colon (rdr)))
                       (thrown-summary
                        #(errors/throw-bad-metadata (rdr) 42))
                       (thrown-summary
                        #(errors/throw-bad-metadata-target (rdr) 42))
                       (thrown-summary
                        #(errors/throw-feature-not-keyword (rdr) 'feature))
                       (thrown-summary
                        #(errors/throw-ns-map-no-map (rdr) 'demo))
                       (thrown-summary
                        #(errors/throw-bad-ns (rdr) 42))
                       (thrown-summary
                        #(errors/throw-bad-reader-tag (rdr) :tag))
                       (thrown-summary
                        #(errors/throw-unknown-reader-tag (rdr) 'demo/tag))]
              :illegal-argument [(thrown-summary
                                  #(errors/throw-invalid-unicode-literal
                                    (rdr)
                                    "12"))
                                 (thrown-summary
                                  #(errors/throw-invalid-unicode-char
                                    (rdr)
                                    "ZZ"))
                                 (thrown-summary
                                  #(errors/throw-invalid-unicode-digit-in-token
                                    (rdr)
                                    \G
                                    "12G"))
                                 (thrown-summary
                                  #(errors/throw-invalid-unicode-digit
                                    (rdr)
                                    \G))
                                 (thrown-summary
                                  #(errors/throw-invalid-unicode-len
                                    (rdr)
                                    2
                                    4))]}))

(emit-case :impl-errors-generated-location-corpus
           (mapv (fn [[source consumed file-name]]
                   (let [r (rt/indexing-push-back-reader source 1 file-name)]
                     (dotimes [_ consumed]
                       (rt/read-char r))
                     (thrown-summary
                      #(errors/reader-error r "seed-" consumed))))
                 [["abc" 0 nil]
                  ["abc" 1 "one.cljc"]
                  ["a\nbc" 2 "two.cljc"]
                  ["a\nbc" 3 "three.cljc"]
                  ["\n\nz" 2 "four.cljc"]
                  ["xy\nz\n" 5 "five.cljc"]]))

(emit-case :impl-inspect-scalar-and-string-contracts
           {:scalars [(inspect/inspect nil)
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
                      (inspect/inspect true "abcdef")
                      (inspect/inspect true "abcde")]
            :direct [(inspect/inspect* false "abcdefghijklmnopqrstu")
                     (inspect/inspect* true "abcdef")]})

(emit-case :impl-inspect-collection-contracts
           {:vectors [(inspect/inspect [])
                      (inspect/inspect [1 2 3])
                      (inspect/inspect [0 1 2 3 4 5 6 7 8 9])
                      (inspect/inspect [0 1 2 3 4 5 6 7 8 9 10])
                      (inspect/inspect true [1 2 3])]
            :lists [(inspect/inspect '())
                    (inspect/inspect '(1 2 3))
                    (inspect/inspect '(0 1 2 3 4 5 6 7 8 9))
                    (inspect/inspect '(0 1 2 3 4 5 6 7 8 9 10))
                    (inspect/inspect true '(1 2 3))]
            :maps [(inspect/inspect {})
                   (inspect/inspect {:a 1})
                   (inspect/inspect true {:a 1})]
            :sets [(inspect/inspect #{})
                   (inspect/inspect #{:a})
                   (inspect/inspect true #{:a})]
            :nested [(inspect/inspect {:a [1 "abcdef"]})
                     (inspect/inspect true {:a [1 "abcdef"]})]})

(emit-case :impl-utils-predicate-and-char-contracts
           {:version-guard utils/<=clojure-1-7-alpha5
            :char [(utils/char nil)
                   (utils/char false)
                   (str (utils/char 65))
                   (str (utils/char \Z))
                   (rejected? #(utils/char "A"))
                   (rejected? #(utils/char -1))]
            :whitespace [(utils/whitespace? nil)
                         (utils/whitespace? \space)
                         (utils/whitespace? \tab)
                         (utils/whitespace? \,)
                         (utils/whitespace? \a)]
            :numeric [(utils/numeric? nil)
                      (utils/numeric? \0)
                      (utils/numeric? \7)
                      (utils/numeric? \a)
                      (utils/numeric? \space)]
            :newline [(utils/newline? nil)
                      (utils/newline? \newline)
                      (utils/newline? \return)
                      (utils/newline? \a)]})

(emit-case :impl-utils-metadata-and-namespace-contracts
           {:desugar-meta [(utils/desugar-meta :private)
                           (utils/desugar-meta 'String)
                           (utils/desugar-meta "String")
                           (utils/desugar-meta '[String Long])
                           (utils/desugar-meta {:a 1})
                           (utils/desugar-meta 42)]
            :namespace-keys (vec (utils/namespace-keys
                                  "demo"
                                  ['a
                                   :b
                                   '_/c
                                   :_/d
                                   'x/y
                                   :x/y
                                   "s"
                                   1]))
            :second' [(utils/second' [])
                      (utils/second' [nil 2])
                      (utils/second' [false 2])
                      (utils/second' [1 2])
                      (utils/second' [nil false])]})

(emit-case :impl-utils-macro-var-and-ex-info-contracts
           (let [v (utils/make-var)]
             {:compile-when [(utils/compile-when true [:compiled 1])
                             (utils/compile-when false [:not-compiled])
                             (utils/compile-when
                              (not utils/<=clojure-1-7-alpha5)
                              :modern)]
              :ex-info? [(utils/ex-info? (ex-info "x" {:a 1}))
                         (utils/ex-info? #?(:clj (RuntimeException. "x")
                                            :lpy (python/Exception "x")))
                         (utils/ex-info? nil)]
              :make-var {:var? (var? v)
                         :thread-bound? (thread-bound? v)
                         :var-get-rejected? (rejected? #(var-get v))
                         :var-set-rejected? (rejected? #(var-set v 1))}}))

(emit-case :edn-adversarial-rejection-corpus
           (mapv (fn [source]
                   {:source source
                    :rejected? (rejected? #(edn/read-string source))})
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
                  "#b \"x\""
                  "#f \"x\""
                  "#unknown/tag 1"]))

(emit-case :edn-generated-corpus
           (mapv (fn [source]
                   {:source source
                    :value (normalize-form (edn/read-string source))})
                 ["nil"
                  "true"
                  "false"
                  "42"
                  "-7"
                  "3.5"
                  "-0.0"
                  "##Inf"
                  "##-Inf"
                  "##NaN"
                  "alpha"
                  "alpha/beta"
                  "/"
                  ":kw"
                  ":ns/kw"
                  "\"line\\nquote\\\"slash\\\\\""
                  "\\newline"
                  "(1 2 3)"
                  "[1 {:a #{:b :c}}]"
                  "{:a 1 :b [2 3]}"
                  "#{:a :b :c}"
                  "#:ns{:a 1 :b 2}"
                  "'a"
                  "^:private a"
                  "#_ :discard 42"]))

(emit-case :adversarial-read-corpus
           (mapv read-summary
                 ["nil"
                  "true"
                  "false"
                  "42"
                  "-7"
                  "3.5"
                  "-0.0"
                  "##Inf"
                  "##-Inf"
                  "##NaN"
                  "alpha"
                  "alpha/beta"
                  "/"
                  ":kw"
                  ":ns/kw"
                  "\"line\\nquote\\\"slash\\\\\""
                  "(1 2 3)"
                  "[1 {:a #{:b :c}}]"
                  "{:a 1 :b [2 3]}"
                  "#{:a :b :c}"
                  "#_ :discard 42"
                  "; comment before form\n42"
                  "#?(:clj :selected :lpy :selected :default :wrong)"
                  "#?(:clj [:selected 1] :lpy [:selected 1])"]))

(emit-case :adversarial-rejection-corpus
           (mapv (fn [source]
                   {:source source
                    :rejected? (rejected? #(tr/read-string source))})
                 ["]"
                  "(1 2"
                  "[1 2"
                  "{:a 1"
                  "#{:a"
                  "foo/bar/baz"
                  "#?(:clj :x :lpy :x)"
                  "#?@(:clj [1] :lpy [1])"]))

(emit-case :adversarial-reader-conditional-splicing
           (let [sources ["[0 #?@(:clj [1 2] :lpy [1 2]) 3]"
                          "(0 #?@(:clj [1 2] :lpy [1 2]) 3)"
                          "{:a 1 #?@(:clj [:b 2] :lpy [:b 2]) :c 3}"
                          "[#_ :discard #?@(:clj [:kept] :lpy [:kept])]"
                          "#?(:clj [#?@(:clj [1 2] :lpy [1 2])]
                              :lpy [#?@(:clj [1 2] :lpy [1 2])])"]]
             (mapv read-summary sources)))

(emit-case :adversarial-location-metadata
           (let [sources ["alpha"
                          "  beta"
                          "\n  gamma"
                          "alpha/beta"
                          "[alpha\n beta\n  gamma]"]
                 summarize (fn [source]
                             (let [value (tr/read-string source)
                                   target (if (vector? value)
                                            (nth value 2)
                                            value)]
                               {:source source
                                :value (normalize-form value)
                                :meta (select-keys (meta target)
                                                   [:line :column
                                                    :end-line :end-column])}))]
             (mapv summarize sources)))

(emit-case :adversarial-source-logging-corpus
           (let [source "  #_ :drop\n[1 #?(:clj :selected :lpy :selected)]\n ; c1\n{:x 0 #?@(:clj [:y 1 :z 2] :lpy [:y 1 :z 2])}\n42"
                 r (rt/source-logging-push-back-reader source)]
             [(tr/read+string {:read-cond :allow
                               :features #{#?(:clj :clj :lpy :lpy)}
                               :eof :done}
                              r)
              (tr/read+string {:read-cond :allow
                               :features #{#?(:clj :clj :lpy :lpy)}
                               :eof :done}
                              r)
              (tr/read+string {:read-cond :allow
                               :features #{#?(:clj :clj :lpy :lpy)}
                               :eof :done}
                              r)
              (tr/read+string {:read-cond :allow
                               :features #{#?(:clj :clj :lpy :lpy)}
                               :eof :done}
                              r)]))

(emit-case :reader-dynamic-vars
           (let [tag-source "#fixture/box [1 2]"
                 eval-source "#=(+ 20 22)"
                 cond-source "#?(:clj :clj :lpy :lpy :default :default)"
                 preserve-source "#?(:clj [:clj 1] :lpy [:lpy 2])"]
             {:data-reader (binding [tr/*data-readers* {'fixture/box
                                                         (fn [value] [:box value])}]
                             (tr/read-string tag-source))
              :default-reader (binding [tr/*default-data-reader-fn*
                                         (fn [tag value] [:default tag value])]
                                (tr/read-string tag-source))
              :suppress-read (binding [tr/*suppress-read* true]
                               (let [value (tr/read-string tag-source)]
                                 [(tagged-literal? value)
                                  (.-tag value)
                                  (.-form value)]))
              :read-eval [(tr/read-string eval-source)
                          (binding [tr/*read-eval* false]
                            (rejected? #(tr/read-string eval-source)))
                          (binding [tr/*read-eval* :unknown]
                            (rejected? #(tr/read-string "1")))]
              :read-cond [(= #?(:clj :clj :lpy :lpy)
                              (tr/read-string {:read-cond :allow
                                               :features #{#?(:clj :clj :lpy :lpy)}}
                                              cond-source))
                          (let [value (tr/read-string {:read-cond :preserve}
                                                      preserve-source)
                                form #?(:clj (.-form value)
                                        :lpy (:form value))]
                            [(some? form)
                             form])]}))

(emit-case :resolve-symbol-contracts
           {:default [(sym-data (tr/resolve-symbol 'map))
                      (sym-data (tr/resolve-symbol 'clojure.core/map))
                      (sym-data (tr/resolve-symbol 'foo/bar))]
            :alias-map (binding [tr/*alias-map* {'alias.ns 'target.ns}]
                         (sym-data (tr/resolve-symbol 'alias.ns/name)))})

(emit-case :read-regex-contracts
           (let [pattern (tr/read-regex (rt/string-push-back-reader "a+\"")
                                        \" nil nil)]
             {:matches? (boolean (re-find pattern "aaab"))
              :rejects? (not (boolean (re-find pattern "bbb")))
              :eof-rejected? (rejected? #(tr/read-regex
                                          (rt/string-push-back-reader "unterminated")
                                          \" nil nil))}))

(emit-case :read-plus-string-contracts
           (let [r (rt/source-logging-push-back-reader
                    "  [1 :two] \n ; note\n {:x 3}  ")]
             [(tr/read+string r)
              (tr/read+string r)
              (tr/read+string r false :done)
              (rejected? #(tr/read+string (rt/string-push-back-reader "1")))]))

(emit-case :reader-constructors
           (let [string-reader (rt/->StringReader "abc" 3 1)
                 pushback (rt/->PushbackReader (rt/string-reader "ab") nil 2 2)
                 indexed (rt/->IndexingPushbackReader (rt/string-reader "xy")
                                                      5 7 true \x 6 "sample.cljc" false)
                 logging (rt/->SourceLoggingPushbackReader (rt/string-reader "xy")
                                                           2 3 true \x 2 "source.cljc" [] false)]
             {:string-char (rt/read-char string-reader)
              :pushback-char (rt/read-char pushback)
              :indexed {:line (rt/get-line-number indexed)
                        :column (rt/get-column-number indexed)
                        :file (rt/get-file-name indexed)
                        :indexing? (rt/indexing-reader? indexed)}
              :logging {:file (rt/get-file-name logging)
                        :source-logging? (rt/source-logging-reader? logging)}
              :coerced-char (rt/read-char (rt/to-pbr (rt/to-rdr "xy") 2))
              :merged-meta (meta (rt/merge-meta (with-meta 'value {:source :old :a 1})
                                                {:b 2}))}))

(emit-case :reader-types-protocols-and-stream-boundaries
           (let [stream-reader (rt/input-stream-reader (input-bytes "ab"))
                 stream-pbr (rt/input-stream-push-back-reader (input-bytes "cd") 2)
                 constructed-stream (rt/->InputStreamReader (input-bytes "xy") nil)
                 pushed (rt/push-back-reader (rt/string-reader "ef") 2)
                 indexed (rt/indexing-push-back-reader "gh\nij" 2 "expanded.cljc")
                 logging (rt/source-logging-push-back-reader "kl" 2 "logged.cljc")]
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
              :log [(rt/log-source* logging (fn [] :logged))
                    (rt/log-source logging :macro-logged)]}))
