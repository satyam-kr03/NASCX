/****************************************************************************
** Meta object code from reading C++ file 'osgviewer.h'
**
** Created by: The Qt Meta Object Compiler version 68 (Qt 6.4.2)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <memory>
#include "osgviewer.h"
#include <QtCore/qmetatype.h>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'osgviewer.h' doesn't include <QObject>."
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
struct qt_meta_stringdata_omnetpp__qtenv__HeartBeat_t {
    uint offsetsAndSizes[2];
    char stringdata0[26];
};
#define QT_MOC_LITERAL(ofs, len) \
    uint(sizeof(qt_meta_stringdata_omnetpp__qtenv__HeartBeat_t::offsetsAndSizes) + ofs), len 
Q_CONSTINIT static const qt_meta_stringdata_omnetpp__qtenv__HeartBeat_t qt_meta_stringdata_omnetpp__qtenv__HeartBeat = {
    {
        QT_MOC_LITERAL(0, 25)   // "omnetpp::qtenv::HeartBeat"
    },
    "omnetpp::qtenv::HeartBeat"
};
#undef QT_MOC_LITERAL
} // unnamed namespace

Q_CONSTINIT static const uint qt_meta_data_omnetpp__qtenv__HeartBeat[] = {

 // content:
      10,       // revision
       0,       // classname
       0,    0, // classinfo
       0,    0, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       0,       // signalCount

       0        // eod
};

Q_CONSTINIT const QMetaObject omnetpp::qtenv::HeartBeat::staticMetaObject = { {
    QMetaObject::SuperData::link<QObject::staticMetaObject>(),
    qt_meta_stringdata_omnetpp__qtenv__HeartBeat.offsetsAndSizes,
    qt_meta_data_omnetpp__qtenv__HeartBeat,
    qt_static_metacall,
    nullptr,
    qt_incomplete_metaTypeArray<qt_meta_stringdata_omnetpp__qtenv__HeartBeat_t,
        // Q_OBJECT / Q_GADGET
        QtPrivate::TypeAndForceComplete<HeartBeat, std::true_type>
    >,
    nullptr
} };

void omnetpp::qtenv::HeartBeat::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    (void)_o;
    (void)_id;
    (void)_c;
    (void)_a;
}

const QMetaObject *omnetpp::qtenv::HeartBeat::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *omnetpp::qtenv::HeartBeat::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_omnetpp__qtenv__HeartBeat.stringdata0))
        return static_cast<void*>(this);
    return QObject::qt_metacast(_clname);
}

int omnetpp::qtenv::HeartBeat::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = QObject::qt_metacall(_c, _id, _a);
    return _id;
}
namespace {
struct qt_meta_stringdata_omnetpp__qtenv__OsgViewer_t {
    uint offsetsAndSizes[16];
    char stringdata0[26];
    char stringdata1[14];
    char stringdata2[1];
    char stringdata3[22];
    char stringdata4[21];
    char stringdata5[9];
    char stringdata6[7];
    char stringdata7[17];
};
#define QT_MOC_LITERAL(ofs, len) \
    uint(sizeof(qt_meta_stringdata_omnetpp__qtenv__OsgViewer_t::offsetsAndSizes) + ofs), len 
Q_CONSTINIT static const qt_meta_stringdata_omnetpp__qtenv__OsgViewer_t qt_meta_stringdata_omnetpp__qtenv__OsgViewer = {
    {
        QT_MOC_LITERAL(0, 25),  // "omnetpp::qtenv::OsgViewer"
        QT_MOC_LITERAL(26, 13),  // "objectsPicked"
        QT_MOC_LITERAL(40, 0),  // ""
        QT_MOC_LITERAL(41, 21),  // "std::vector<cObject*>"
        QT_MOC_LITERAL(63, 20),  // "setCameraManipulator"
        QT_MOC_LITERAL(84, 8),  // "QAction*"
        QT_MOC_LITERAL(93, 6),  // "sender"
        QT_MOC_LITERAL(100, 16)   // "applyViewerHints"
    },
    "omnetpp::qtenv::OsgViewer",
    "objectsPicked",
    "",
    "std::vector<cObject*>",
    "setCameraManipulator",
    "QAction*",
    "sender",
    "applyViewerHints"
};
#undef QT_MOC_LITERAL
} // unnamed namespace

Q_CONSTINIT static const uint qt_meta_data_omnetpp__qtenv__OsgViewer[] = {

 // content:
      10,       // revision
       0,       // classname
       0,    0, // classinfo
       3,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       1,       // signalCount

 // signals: name, argc, parameters, tag, flags, initial metatype offsets
       1,    1,   32,    2, 0x06,    1 /* Public */,

 // slots: name, argc, parameters, tag, flags, initial metatype offsets
       4,    1,   35,    2, 0x09,    3 /* Protected */,
       7,    0,   38,    2, 0x0a,    5 /* Public */,

 // signals: parameters
    QMetaType::Void, 0x80000000 | 3,    2,

 // slots: parameters
    QMetaType::Void, 0x80000000 | 5,    6,
    QMetaType::Void,

       0        // eod
};

Q_CONSTINIT const QMetaObject omnetpp::qtenv::OsgViewer::staticMetaObject = { {
    QMetaObject::SuperData::link<IOsgViewer::staticMetaObject>(),
    qt_meta_stringdata_omnetpp__qtenv__OsgViewer.offsetsAndSizes,
    qt_meta_data_omnetpp__qtenv__OsgViewer,
    qt_static_metacall,
    nullptr,
    qt_incomplete_metaTypeArray<qt_meta_stringdata_omnetpp__qtenv__OsgViewer_t,
        // Q_OBJECT / Q_GADGET
        QtPrivate::TypeAndForceComplete<OsgViewer, std::true_type>,
        // method 'objectsPicked'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<const std::vector<cObject*> &, std::false_type>,
        // method 'setCameraManipulator'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<QAction *, std::false_type>,
        // method 'applyViewerHints'
        QtPrivate::TypeAndForceComplete<void, std::false_type>
    >,
    nullptr
} };

void omnetpp::qtenv::OsgViewer::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<OsgViewer *>(_o);
        (void)_t;
        switch (_id) {
        case 0: _t->objectsPicked((*reinterpret_cast< std::add_pointer_t<std::vector<cObject*>>>(_a[1]))); break;
        case 1: _t->setCameraManipulator((*reinterpret_cast< std::add_pointer_t<QAction*>>(_a[1]))); break;
        case 2: _t->applyViewerHints(); break;
        default: ;
        }
    } else if (_c == QMetaObject::IndexOfMethod) {
        int *result = reinterpret_cast<int *>(_a[0]);
        {
            using _t = void (OsgViewer::*)(const std::vector<cObject*> & );
            if (_t _q_method = &OsgViewer::objectsPicked; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 0;
                return;
            }
        }
    }
}

const QMetaObject *omnetpp::qtenv::OsgViewer::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *omnetpp::qtenv::OsgViewer::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_omnetpp__qtenv__OsgViewer.stringdata0))
        return static_cast<void*>(this);
    return IOsgViewer::qt_metacast(_clname);
}

int omnetpp::qtenv::OsgViewer::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = IOsgViewer::qt_metacall(_c, _id, _a);
    if (_id < 0)
        return _id;
    if (_c == QMetaObject::InvokeMetaMethod) {
        if (_id < 3)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 3;
    } else if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 3)
            *reinterpret_cast<QMetaType *>(_a[0]) = QMetaType();
        _id -= 3;
    }
    return _id;
}

// SIGNAL 0
void omnetpp::qtenv::OsgViewer::objectsPicked(const std::vector<cObject*> & _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 0, _a);
}
QT_WARNING_POP
QT_END_MOC_NAMESPACE
