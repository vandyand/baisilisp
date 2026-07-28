;; Portable clojure.java.classpath compatibility cases.

(require '[clojure.java.classpath :as cp]
         '[clojure.java.io :as io])

#?(:clj
   (import '(java.io File)
           '(java.net URLClassLoader)
           '(java.util.jar JarFile JarEntry)
           '(java.util.zip ZipEntry ZipOutputStream))
   :lpy
   (import pathlib sys tempfile zipfile))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(defn thrown? [f]
  (try
    (f)
    false
    (catch #?(:clj Throwable :lpy python/Exception) _
      true)))

(defn names [xs]
  (sort (map name xs)))

(defn temp-root []
  #?(:clj (let [file (File/createTempFile "java-classpath-cases" ".tmp")]
            (.delete file)
            (.mkdirs file)
            file)
     :lpy (pathlib/Path (tempfile/mkdtemp ** :prefix "java-classpath-cases"))))

(defn child-path [root & parts]
  #?(:clj (reduce (fn [^File parent part] (File. parent (str part))) root parts)
     :lpy (reduce (fn [parent part] (pathlib/Path parent (str part))) root parts)))

(defn mkdirs! [path]
  #?(:clj (.mkdirs path)
     :lpy (.mkdir path ** :parents true :exist_ok true))
  path)

(defn write-jar! [path entries]
  #?(:clj
     (with-open [stream (ZipOutputStream. (io/output-stream path))]
       (doseq [[name text] entries]
         (.putNextEntry stream (ZipEntry. name))
         (.write stream (.getBytes (str text) "UTF-8"))
         (.closeEntry stream)))
     :lpy
     (with-open [archive (zipfile/ZipFile path "w")]
       (doseq [[name text] entries]
         (.writestr archive name (str text)))))
  path)

(defn abs-path [path]
  #?(:clj (.getAbsolutePath path)
     :lpy (str (.resolve path))))

(defn path-name [path]
  #?(:clj (.getName path)
     :lpy (.-name path)))

(defn file-url [path]
  #?(:clj (.toURL (.toURI path))
     :lpy (.as_uri (.resolve path))))

(defn jar-entry-names [jar]
  (sort (cp/filenames-in-jar jar)))

(defn zip-jar [path]
  #?(:clj (JarFile. path)
     :lpy (zipfile/ZipFile path)))

#?(:clj
   (defn loader-for [paths]
     (URLClassLoader. (into-array (map file-url paths)) nil))
   :lpy
   (do
     (defrecord URLLoader [entries])
     (extend-type URLLoader
       cp/URLClasspath
       (urls [loader] (:entries loader)))
     (defn loader-for [paths]
       (->URLLoader (map file-url paths)))))

(emit-case :public-surface
           (names (keys (ns-publics 'clojure.java.classpath))))

(emit-case :jar-file-boundaries
           (let [root (temp-root)
                 jar (write-jar! (child-path root "fixture.jar")
                                 [["alpha/core.cljc" "(ns alpha.core)"]
                                  ["alpha/nested/item.clj" "(ns alpha.nested.item)"]
                                  ["META-INF/data.txt" "data"]])
                 upper (write-jar! (child-path root "fixture-upper.JAR")
                                   [["upper/core.clj" "(ns upper.core)"]])
                 txt (child-path root "not-a-jar.txt")]
             #?(:clj (spit txt "plain")
                :lpy (.write_text txt "plain"))
             {:jar? [(cp/jar-file? jar)
                     (cp/jar-file? upper)
                     (not (cp/jar-file? txt))
                     (not (cp/jar-file? (child-path root "missing.jar")))]
              :entries (jar-entry-names (zip-jar jar))
              :nil-boundary (thrown? #(cp/jar-file? nil))}))

(emit-case :loader-and-system-classpath
           (let [root (temp-root)
                 dir (mkdirs! (child-path root "classes"))
                 jar (write-jar! (child-path root "classes.jar")
                                 [["demo/core.clj" "(ns demo.core)"]])
                 loader (loader-for [dir jar])
                 loader-paths (map path-name (cp/loader-classpath loader))
                 classloader-paths (map path-name (cp/classpath loader))
                 system-paths (take 5 (cp/system-classpath))
                 default-paths (take 5 (cp/classpath))]
             {:get-urls-count (count (cp/get-urls loader))
              :loader-paths loader-paths
              :classpath-paths classloader-paths
              :nil-loader [(nil? (cp/get-urls nil))
                            (thrown? #(cp/urls nil))
                            (empty? (cp/loader-classpath nil))
                            (empty? (cp/classpath nil))]
              :system-non-empty (boolean (seq system-paths))
              :default-non-empty (boolean (seq default-paths))}))

(emit-case :directory-and-jarfile-filters
           {:directory-names-are-strings
            (every? string?
                    (map path-name (take 5 (cp/classpath-directories))))
            :jar-entry-groups-are-seqs
            (every? sequential?
                    (map #(take 3 (cp/filenames-in-jar %))
                         (take 5 (cp/classpath-jarfiles))))
            :directory-count-number? (number? (count (cp/classpath-directories)))
            :jarfile-count-number? (number? (count (cp/classpath-jarfiles)))})
