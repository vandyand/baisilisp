;; Portable clojure.core host/resource/printing utility residual semantics.
;; Host objects, files, and runtime-specific munging encodings are normalized
;; into deterministic data before comparison.

(require '[clojure.string :as str])

#?(:clj (import '[java.io File]
                'java.util.Vector)
   :lpy (import pathlib shutil tempfile types))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn rejected? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn temp-root []
  #?(:clj (let [file (File/createTempFile "core-host-print-resource" "dir")]
            (.delete file)
            (.mkdir file)
            file)
     :lpy (pathlib/Path (tempfile/mkdtemp ** :prefix "core-host-print-resource"))))

(defn child-path [root rel]
  #?(:clj (File. root rel)
     :lpy (.joinpath root rel)))

(defn mkdir! [root rel]
  #?(:clj (.mkdirs (child-path root rel))
     :lpy (.mkdir (child-path root rel) ** :parents true :exist_ok true)))

(defn write-file! [root rel text]
  #?(:clj (spit (child-path root rel) text)
     :lpy (.write-text (child-path root rel) text)))

(defn delete-tree! [root]
  (try
    #?(:clj (letfn [(delete-file [file]
                     (when (.isDirectory file)
                       (doseq [child (.listFiles file)]
                         (delete-file child)))
                     (.delete file))]
              (delete-file root))
       :lpy (shutil/rmtree root))
    (catch #?(:clj Throwable :lpy python/Exception) _
      nil)))

(defn relative-name [root file]
  #?(:clj (if (= (.getCanonicalFile root) (.getCanonicalFile file))
            "."
            (str/replace (str (.relativize (.toPath root) (.toPath file)))
                         "\\"
                         "/"))
     :lpy (.as-posix (.relative-to file root))))

(defn file-seq-summary [root]
  (sort (map #(relative-name root %) (file-seq root))))

(defn make-bean-target []
  #?(:clj (java.awt.Point. 2 3)
     :lpy (types/SimpleNamespace ** :x 2 :y 3)))

(defn enumeration-target [xs]
  #?(:clj (.elements (doto (Vector.)
                       (.addAll xs)))
     :lpy xs))

(defn classpath-target [root]
  #?(:clj (.toURL (.toURI root))
     :lpy root))

(defrecord HostPrintResourceRecord [value])

(defmethod print-method HostPrintResourceRecord
  [x writer]
  (.write writer (str "<" (:value x) ">")))

(defmethod print-dup HostPrintResourceRecord
  [x writer]
  (.write writer (str "dup:" (:value x))))

(emit-case :host-bean-enumeration-and-classpath-boundaries
           (let [bean-value (bean (make-bean-target))
                 empty-enum (enumeration-target [])]
             {:bean {:x (long (:x bean-value))
                     :y (long (:y bean-value))
                     :class? (contains? bean-value :class)}
              :enumeration [(vec (enumeration-seq (enumeration-target [1 2 3])))
                            (nil? (seq (enumeration-seq empty-enum)))]
              :add-classpath (let [root (temp-root)]
                               (try
                                 (let [result (atom nil)]
                                   (with-out-str
                                     (reset! result
                                             (boolean
                                              (try
                                                (nil? (add-classpath
                                                       (classpath-target root)))
                                                (catch #?(:clj Throwable
                                                          :lpy python/Exception) _
                                                  true)))))
                                   @result)
                                 (finally
                                   (delete-tree! root))))}))

(emit-case :file-seq-temp-tree-contracts
           (let [root (temp-root)]
             (try
               (mkdir! root "dir")
               (mkdir! root "dir/nested")
               (write-file! root "a.txt" "a")
               (write-file! root "dir/b.txt" "b")
               (write-file! root "dir/nested/c.txt" "c")
               (file-seq-summary root)
               (finally
                 (delete-tree! root)))))

(emit-case :file-seq-seeded-tree-fuzz
           (mapv (fn [n]
                   (let [root (temp-root)
                         dir (str "d" n)
                         nested (str dir "/n" (mod (* n 7) 5))
                         a (str "root-" n ".txt")
                         b (str dir "/leaf-" (* n n) ".txt")
                         c (str nested "/deep-" (+ n 11) ".txt")]
                     (try
                       (mkdir! root nested)
                       (write-file! root a (str n))
                       (write-file! root b (str (* n n)))
                       (write-file! root c (str (+ n 11)))
                       {:n n
                        :paths (file-seq-summary root)}
                       (finally
                         (delete-tree! root)))))
                 (range 6)))

(emit-case :printing-multimethod-contracts
           (let [value (->HostPrintResourceRecord "v")]
             {:print-method (with-out-str (print-method value *out*))
              :print-dup-direct (with-out-str (print-dup value *out*))
              :print-dup-pr-str (binding [*print-dup* true]
                                  (pr-str value))
              :methods [(contains? (methods print-method)
                                   HostPrintResourceRecord)
                        (contains? (methods print-dup)
                                   HostPrintResourceRecord)]}))

(emit-case :munge-and-namespace-munge-contracts
           (let [munged (munge "alpha-beta?+!")
                 ns-munged (namespace-munge "alpha-beta.gamma-delta")]
             {:munge [(string? munged)
                      (not (str/includes? munged "-"))
                      (not (str/includes? munged "?"))
                      (not (str/includes? munged "+"))
                      (not (str/includes? munged "!"))
                      (= "plain" (munge "plain"))]
              :namespace-munge [(string? ns-munged)
                                (= "alpha_beta.gamma_delta" ns-munged)]}))

(emit-case :use-and-compile-boundaries
           (do
             (use '[clojure.string :only [blank?] :rename {blank? host-blank?}])
             (let [host-blank-var (ns-resolve *ns* 'host-blank?)]
               {:use [(host-blank-var " ")
                      (not (host-blank-var "x"))]
                :compile-missing (rejected?
                                  #(compile 'core-host-print-resource.missing-ns))})))
