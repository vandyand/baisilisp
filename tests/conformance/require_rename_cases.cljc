;; Clojure libspec :rename applies only to Vars selected for referral.  It must
;; not discard selected Vars which do not appear in the rename map.

(ns conformance.require-rename-cases
  (:require [clojure [string :refer [lower-case]
                             :rename {lower-case lower}]]))

(defn emit-case [case value]
  (println (pr-str {:case case :value value})))

(emit-case :ns-prefix-require-rename
           {:renamed (lower "PREFIX")
            :original-present? (boolean (resolve 'lower-case))})

(require '[clojure.string :refer :all
                          :exclude [lower-case]
                          :rename {upper-case upper}])

(emit-case :refer-all-rename-and-exclude
           {:renamed (upper "prefix")
            :original-present? (boolean (resolve 'upper-case))
            :excluded-present? (boolean (resolve 'lower-case))})

(require '[clojure.string :refer [upper-case]
                          :rename {lower-case discarded}])

(emit-case :unmapped-rename-preserves-refer
           {:value (upper-case "prefix")
            :discarded-present? (boolean (resolve 'discarded))})
