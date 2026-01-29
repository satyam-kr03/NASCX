/****************************************************************************
** Meta object code from reading C++ file 'layouterenv.h'
**
** Created by: The Qt Meta Object Compiler version 68 (Qt 6.4.2)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <memory>
#include "layouterenv.h"
#include <QtCore/qmetatype.h>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'layouterenv.h' doesn't include <QObject>."
#elif Q_MOC_OUTPUT_REVISION != 68
#error "This file was generated using the moc from 6.4.2. It"
#error "cannot be used with the include files from this version of Qt."
#error "(The moc has changed too much.)"
#endif

#ifndef Q_CONSTINIT
#define Q_CONSTINIT
#endif

QT_BEGIN_MOC_NAMESPACE
QT_WARNING_PUSH
QT_WARNING_DISABLE_DEPRECATED
namespace {
struct qt_meta_stringdata_omnetpp__qtenv__QtenvGraphLayouterEnvironment_t {
    uint offsetsAndSizes[6];
    char stringdata0[46];
    char stringdata1[5];
    char stringdata2[1];
};
#define QT_MOC_LITERAL(ofs, len) \
    uint(sizeof(qt_meta_stringdata_omnetpp__qtenv__QtenvGraphLayouterEnvironment_t::offsetsAndSizes) + ofs), len 
Q_CONSTINIT static const qt_meta_stringdata_omnetpp__qtenv__QtenvGraphLayouterEnvironment_t qt_meta_stringdata_omnetpp__qtenv__QtenvGraphLayouterEnvironment = {
    {
        QT_MOC_LITERAL(0, 45),  // "omnetpp::qtenv::QtenvGraphLay..."
        QT_MOC_LITERAL(46, 4),  // "stop"
        QT_MOC_LITERAL(51, 0)   // ""
    },
    "omnetpp::qtenv::QtenvGraphLayouterEnvironment",
    "stop",
    ""
};
#undef QT_MOC_LITERAL
} // unnamed namespace

Q_CONSTINIT static const uint qt_meta_data_omnetpp__qtenv__QtenvGraphLayouterEnvironment[] = {

 // content:
      10,       // revision
       0,       // classname
       0,    0, // classinfo
       1,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       0,       // signalCount

 // slots: name, argc, parameters, tag, flags, initial metatype offsets
       1,    0,   20,    2, 0x0a,    1 /* Public */,

 // slots: parameters
    QMetaType::Void,

       0        // eod
};

Q_CONSTINIT const QMetaObject omnetpp::qtenv::QtenvGraphLayouterEnvironment::staticMetaObject = { {
    QMetaObject::SuperData::link<QObject::staticMetaObject>(),
    qt_meta_stringdata_omnetpp__qtenv__QtenvGraphLayouterEnvironment.offsetsAndSizes,
    qt_meta_data_omnetpp__qtenv__QtenvGraphLayouterEnvironment,
    qt_static_metacall,
    nullptr,
    qt_incomplete_metaTypeArray<qt_meta_stringdata_omnetpp__qtenv__QtenvGraphLayouterEnvironment_t,
        // Q_OBJECT / Q_GADGET
        QtPrivate::TypeAndForceComplete<QtenvGraphLayouterEnvironment, std::true_type>,
        // method 'stop'
        QtPrivate::TypeAndForceComplete<void, std::false_type>
    >,
    nullptr
} };

void omnetpp::qtenv::QtenvGraphLayouterEnvironment::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<QtenvGraphLayouterEnvironment *>(_o);
        (void)_t;
        switch (_id) {
        case 0: _t->stop(); break;
        default: ;
        }
    }
    (void)_a;
}

const QMetaObject *omnetpp::qtenv::QtenvGraphLayouterEnvironment::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *omnetpp::qtenv::QtenvGraphLayouterEnvironment::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_omnetpp__qtenv__QtenvGraphLayouterEnvironment.stringdata0))
        return static_cast<void*>(this);
    if (!strcmp(_clname, "GraphLayouterEnvironment"))
        return static_cast< GraphLayouterEnvironment*>(this);
    return QObject::qt_metacast(_clname);
}

int omnetpp::qtenv::QtenvGraphLayouterEnvironment::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = QObject::qt_metacall(_c, _id, _a);
    if (_id < 0)
        return _id;
    if (_c == QMetaObject::InvokeMetaMethod) {
        if (_id < 1)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 1;
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 1)
            *reinterpret_cast<QMetaType *>(_a[0]) = QMetaType();
        _id -= 1;
    }
    return _id;
}
QT_WARNING_POP
QT_END_MOC_NAMESPACE
