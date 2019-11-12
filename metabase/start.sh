# To workaround https://github.com/metabase/metabase/issues/8373
HOSTNAME=`cat /etc/hostname`
echo "HOSTNAME: ${HOSTNAME}"
echo "127.0.0.1 ${HOSTNAME}" >> /etc/hosts

echo "/etc/hosts:"
cat /etc/hosts

/app/run_metabase.sh "$@"
