/****************************************************************************
** Meta object code from reading C++ file 'timelinegraphicsview.h'
**
** Created by: The Qt Meta Object Compiler version 68 (Qt 6.4.2)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include <memory>
#include "timelinegraphicsview.h"
#include <QtCore/qmetatype.h>
#include <QtCore/QList>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'timelinegraphicsview.h' doesn't include <QObject>."
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
struct qt_meta_stringdata_omnetpp__qtenv__TimeLineGraphicsView_t {
    uint offsetsAndSizes[20];
    char stringdata0[37];
    char stringdata1[21];
    char stringdata2[1];
    char stringdata3[16];
    char stringdata4[8];
    char stringdata5[10];
    char stringdata6[6];
    char stringdata7[9];
    char stringdata8[7];
    char stringdata9[12];
};
#define QT_MOC_LITERAL(ofs, len) \
    uint(sizeof(qt_meta_stringdata_omnetpp__qtenv__TimeLineGraphicsView_t::offsetsAndSizes) + ofs), len 
Q_CONSTINIT static const qt_meta_stringdata_omnetpp__qtenv__TimeLineGraphicsView_t qt_meta_stringdata_omnetpp__qtenv__TimeLineGraphicsView = {
    {
        QT_MOC_LITERAL(0, 36),  // "omnetpp::qtenv::TimeLineGraph..."
        QT_MOC_LITERAL(37, 20),  // "contextMenuRequested"
        QT_MOC_LITERAL(58, 0),  // ""
        QT_MOC_LITERAL(59, 15),  // "QList<cObject*>"
        QT_MOC_LITERAL(75, 7),  // "objects"
        QT_MOC_LITERAL(83, 9),  // "globalPos"
        QT_MOC_LITERAL(93, 5),  // "click"
        QT_MOC_LITERAL(99, 8),  // "cObject*"
        QT_MOC_LITERAL(108, 6),  // "object"
        QT_MOC_LITERAL(115, 11)   // "doubleClick"
    },
    "omnetpp::qtenv::TimeLineGraphicsView",
    "contextMenuRequested",
    "",
    "QList<cObject*>",
    "objects",
    "globalPos",
    "click",
    "cObject*",
    "object",
    "doubleClick"
};
#undef QT_MOC_LITERAL
} // unnamed namespace

Q_CONSTINIT static const uint qt_meta_data_omnetpp__qtenv__TimeLineGraphicsView[] = {

 // content:
      10,       // revision
       0,       // classname
       0,    0, // classinfo
       3,   14, // methods
       0,    0, // properties
       0,    0, // enums/sets
       0,    0, // constructors
       0,       // flags
       3,       // signalCount

 // signals: name, argc, parameters, tag, flags, initial metatype offsets
       1,    2,   32,    2, 0x06,    1 /* Public */,
       6,    1,   37,    2, 0x06,    4 /* Public */,
       9,    1,   40,    2, 0x06,    6 /* Public */,

 // signals: parameters
    QMetaType::Void, 0x80000000 | 3, QMetaType::QPoint,    4,    5,
    QMetaType::Void, 0x80000000 | 7,    8,
    QMetaType::Void, 0x80000000 | 7,    8,

       0        // eod
};

Q_CONSTINIT const QMetaObject omnetpp::qtenv::TimeLineGraphicsView::staticMetaObject = { {
    QMetaObject::SuperData::link<QGraphicsView::staticMetaObject>(),
    qt_meta_stringdata_omnetpp__qtenv__TimeLineGraphicsView.offsetsAndSizes,
    qt_meta_data_omnetpp__qtenv__TimeLineGraphicsView,
    qt_static_metacall,
    nullptr,
    qt_incomplete_metaTypeArray<qt_meta_stringdata_omnetpp__qtenv__TimeLineGraphicsView_t,
        // Q_OBJECT / Q_GADGET
        QtPrivate::TypeAndForceComplete<TimeLineGraphicsView, std::true_type>,
        // method 'contextMenuRequested'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<QVector<cObject*>, std::false_type>,
        QtPrivate::TypeAndForceComplete<QPoint, std::false_type>,
        // method 'click'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<cObject *, std::false_type>,
        // method 'doubleClick'
        QtPrivate::TypeAndForceComplete<void, std::false_type>,
        QtPrivate::TypeAndForceComplete<cObject *, std::false_type>
    >,
    nullptr
} };

void omnetpp::qtenv::TimeLineGraphicsView::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    if (_c == QMetaObject::InvokeMetaMethod) {
        auto *_t = static_cast<TimeLineGraphicsView *>(_o);
        (void)_t;
        switch (_id) {
        case 0: _t->contextMenuRequested((*reinterpret_cast< std::add_pointer_t<QList<cObject*>>>(_a[1])),(*reinterpret_cast< std::add_pointer_t<QPoint>>(_a[2]))); break;
        case 1: _t->click((*reinterpret_cast< std::add_pointer_t<cObject*>>(_a[1]))); break;
        case 2: _t->doubleClick((*reinterpret_cast< std::add_pointer_t<cObject*>>(_a[1]))); break;
        default: ;
        }
    } else if (_c == QMetaObject::IndexOfMethod) {
        int *result = reinterpret_cast<int *>(_a[0]);
        {
            using _t = void (TimeLineGraphicsView::*)(QVector<cObject*> , QPoint );
            if (_t _q_method = &TimeLineGraphicsView::contextMenuRequested; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 0;
                return;
            }
        }
        {
            using _t = void (TimeLineGraphicsView::*)(cObject * );
            if (_t _q_method = &TimeLineGraphicsView::click; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 1;
                return;
            }
        }
        {
            using _t = void (TimeLineGraphicsView::*)(cObject * );
            if (_t _q_method = &TimeLineGraphicsView::doubleClick; *reinterpret_cast<_t *>(_a[1]) == _q_method) {
                *result = 2;
                return;
            }
        }
    }
}

const QMetaObject *omnetpp::qtenv::TimeLineGraphicsView::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *omnetpp::qtenv::TimeLineGraphicsView::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_meta_stringdata_omnetpp__qtenv__TimeLineGraphicsView.stringdata0))
        return static_cast<void*>(this);
    return QGraphicsView::qt_metacast(_clname);
}

int omnetpp::qtenv::TimeLineGraphicsView::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = QGraphicsView::qt_metacall(_c, _id, _a);
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
void omnetpp::qtenv::TimeLineGraphicsView::contextMenuRequested(QVector<cObject*> _t1, QPoint _t2)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))), const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t2))) };
    QMetaObject::activate(this, &staticMetaObject, 0, _a);
}

// SIGNAL 1
void omnetpp::qtenv::TimeLineGraphicsView::click(cObject * _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 1, _a);
}

// SIGNAL 2
void omnetpp::qtenv::TimeLineGraphicsView::doubleClick(cObject * _t1)
{
    void *_a[] = { nullptr, const_cast<void*>(reinterpret_cast<const void*>(std::addressof(_t1))) };
    QMetaObject::activate(this, &staticMetaObject, 2, _a);
}
QT_WARNING_POP
QT_END_MOC_NAMESPACE
