;; Portable clojure.tools.reader/basilisp.tools.reader public surface and
;; reader-types constructor/coercer behavior.

(require '[clojure.tools.reader :as tr]
         '[clojure.tools.reader.reader-types :as rt])

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

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

(emit-case :map-func
           [(tr/map-func (range 15))
            (tr/map-func (range 16))])

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
