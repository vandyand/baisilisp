;; Portable clojure.core reader/eval/load boundary semantics. Host-specific
;; readers, temp files, and load suffixes are normalized so emitted values are
;; data-only and deterministic.

#?(:clj (import '[java.io StringReader File]
                'clojure.lang.LineNumberingPushbackReader)
   :lpy (import io os tempfile))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn reader [source]
  #?(:clj (LineNumberingPushbackReader. (StringReader. source))
     :lpy (io/StringIO source)))

(defn temp-path []
  #?(:clj (let [f (File/createTempFile "core-reader-load" ".clj")]
            (.getAbsolutePath f))
     :lpy (let [f (tempfile/NamedTemporaryFile ** :delete false
                                               :prefix "core-reader-load"
                                               :suffix ".lpy")
                path (.-name f)]
            (.close f)
            path)))

(defn delete-path [path]
  (try
    #?(:clj (.delete (File. path))
       :lpy (os/remove path))
    (catch #?(:clj Throwable :lpy python/Exception) _
      nil)))

(def ^{:test (fn [] :metadata-test-ran)} metadata-tested-root :root)
(def metadata-untested-root :root)

(emit-case :read-and-read-plus-string-boundaries
           (let [r (reader "  (+ 1 2)  :next")
                 eof-reader (reader "")]
             {:read [(read (reader "  [:a 1]"))
                     (read (reader "") false :done)
                     (rejected? #(read (reader "") true :done))
                     (binding [*in* (reader ":from-in")]
                       (read))]
              :read+string [(read+string r)
                            (read+string r)
                            (read+string {:eof :done} eof-reader)]
              :reader-conditional [(rejected?
                                    #(read-string "#?(:clj :clj :lpy :lpy)"))
                                   (= #?(:clj :clj :lpy :lpy)
                                      (read-string {:read-cond :allow}
                                                   "#?(:clj :clj :lpy :lpy)"))
                                   (reader-conditional?
                                    (read-string {:read-cond :preserve}
                                                 "#?(:clj :clj :lpy :lpy)"))
                                   (let [rc (reader-conditional
                                             '(:clj :clj :lpy :lpy)
                                             false)]
                                     [(reader-conditional? rc)
                                      (:form rc)
                                      (:splicing? rc)])
                                   (rejected?
                                    #(read-string "[1 #?(:clj :clj :lpy :lpy)]"))]}))

(emit-case :tagged-literal-and-metadata-helpers
           (let [tagged (tagged-literal 'fixture/tag {:a [1 2]})
                 a (atom 1)]
             {:tagged [(tagged-literal? tagged)
                       (= 'fixture/tag (:tag tagged))
                       (:form tagged)]
              :reset-meta [(meta (reset-meta! a {:a 1}))
                           (meta (reset-meta! a nil))]
              :test [(test #'metadata-tested-root)
                     (test #'metadata-untested-root)]}))

(emit-case :eval-load-reader-load-string
           {:eval [(eval '(+ 1 2 3))
                   (eval "runtime-value")
                   (let [n (create-ns 'core-reader-eval-load.eval-target)]
                     (try
                       (binding [*ns* n]
                         (eval '(def eval-target-value 44))
                         (eval 'eval-target-value))
                       (finally
                         (remove-ns 'core-reader-eval-load.eval-target))))]
            :load-reader (load-reader (reader "(def load_reader_probe 11)
                                               (+ load_reader_probe 4)"))
            :load-reader-reader-cond (rejected?
                                      #(load-reader
                                        (reader "#?(:clj :clj :lpy :lpy)")))
            :load-string (load-string "(def load_string_probe 17)
                                      (+ load_string_probe 5)")
            :load-string-reader-cond (rejected?
                                      #(load-string "#?(:clj :clj :lpy :lpy)"))})

(emit-case :load-file-and-load
           (let [path (temp-path)]
             (try
               (spit path "(def load_file_probe 29)\n(+ load_file_probe 13)")
               {:load-file (load-file path)
                :load-missing (rejected?
                               #(load "/tests/conformance/missing_load_probe"))}
               (finally
                 (delete-path path)))))

(emit-case :seeded-reader-eval-load-fuzz
           (mapv (fn [n]
                   (let [source (str "(+ " n " " (* n n) ")")
                         pair-source (str "  " source "  :tail")
                         r (reader pair-source)]
                     {:n n
                      :read-string (read-string source)
                      :read (read (reader source))
                      :eval (eval (read-string source))
                      :read+string (read+string r)}))
                 (range -6 7)))
